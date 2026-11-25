#include <circle/usb/usbsubmission.h>
namespace {
u32 g_SubmissionGenerationGate;
u64 g_SubmissionGeneration;
class CTrySubmissionGate {
 u32 *p;boolean held;
public:
 explicit CTrySubmissionGate(u32 *gate):p(gate),held(FALSE){u32 expected=0;held=__atomic_compare_exchange_n(p,&expected,1,TRUE,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);}
 ~CTrySubmissionGate(){if(held)__atomic_store_n(p,0,__ATOMIC_RELEASE);}
 boolean Locked()const{return held;}
 CTrySubmissionGate(const CTrySubmissionGate&)=delete;
 CTrySubmissionGate&operator=(const CTrySubmissionGate&)=delete;
};
}
extern "C" u32 circle_usb_submission_api_version(void){return 1;}
TUSBSubmissionResult CUSBSubmissionPool::Find(TUSBSubmissionHandle h,TRecord **out){
 if(h.Slot>=MaxSubmissions||!h.Generation)return SubmissionInvalid;
 TRecord &r=m_Records[h.Slot];if(r.Generation!=h.Generation)return SubmissionStale;
 *out=&r;return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::FindStage(TUSBSubmissionStage s,TRecord **out){
 if(!s.Serial)return SubmissionInvalid;
 auto result=Find(s.Submission,out);if(result!=SubmissionOK)return result;
 if((*out)->StageSerial!=s.Serial)return SubmissionStale;
 return SubmissionOK;
}
void CUSBSubmissionPool::CopySnapshot(const TRecord&r,TUSBSubmissionSnapshot*out){
 out->State=r.State;out->Outcome=r.Outcome;out->Resources=r.Resources;
 out->StageSerial=r.StageSerial;out->CompletedStages=r.CompletedStages;out->ControllerReferences=r.References;
 out->StageCompleted=r.StageDone;out->CancellationRequested=r.CancelRequested;
 out->TerminalRequested=r.State==SubmissionTerminalPending||r.State==SubmissionDispatched;
 out->TerminalCallbackDispatched=r.State==SubmissionDispatched;
 out->StageError=r.StageError;out->FirstError=r.FirstError;out->CancellationError=r.CancelError;out->TerminalError=r.TerminalError;
}
TUSBSubmissionResult CUSBSubmissionPool::Begin(TUSBSubmissionResources resources,TUSBSubmissionCallback*fn,void*ctx,TUSBSubmissionHandle*out){
 if(!out||!fn||!resources.Request||resources.RequestOwner>SubmissionControllerOwned||resources.BufferOwner>SubmissionControllerOwned||resources.ContextOwner>SubmissionControllerOwned)return SubmissionInvalid;
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 unsigned free=MaxSubmissions;
 for(unsigned i=0;i<MaxSubmissions;i++) {
  if(m_Records[i].Generation&&m_Records[i].Resources.Request==resources.Request)return SubmissionAlready;
  if(free==MaxSubmissions&&!m_Records[i].Generation)free=i;
 }
 if(free==MaxSubmissions)return SubmissionNoCapacity;
 CTrySubmissionGate generation(&g_SubmissionGenerationGate);if(!generation.Locked())return SubmissionBusy;
 if(g_SubmissionGeneration==(u64)-1)return SubmissionExhausted;
 TRecord&r=m_Records[free];r={};r.Generation=++g_SubmissionGeneration;r.State=SubmissionOpen;r.Resources=resources;r.Callback=fn;r.Context=ctx;
 out->Generation=r.Generation;out->Slot=free;return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::BeginStage(TUSBSubmissionHandle h,TUSBSubmissionStage*out){
 if(!out)return SubmissionInvalid;
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=Find(h,&r);if(result!=SubmissionOK)return result;
 if(r->State!=SubmissionOpen||r->CancelRequested||r->FirstError)return SubmissionWrongState;
 if(r->StageSerial&&(!r->StageDone||r->References))return SubmissionReferenced;
 if(r->StageSerial==(u64)-1)return SubmissionExhausted;
 ++r->StageSerial;r->StageDone=FALSE;r->StageError=0;out->Submission=h;out->Serial=r->StageSerial;return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::RetainController(TUSBSubmissionStage s,TUSBSubmissionReferenceKind kind,TUSBSubmissionReference*out){
 if(!out||kind>SubmissionCompletionReference)return SubmissionInvalid;
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=FindStage(s,&r);if(result!=SubmissionOK)return result;
 if(r->State!=SubmissionOpen||r->CancelRequested||r->StageDone)return SubmissionWrongState;
 if(r->References>=MaxReferences)return SubmissionNoCapacity;
 unsigned free=MaxReferences;for(unsigned i=0;i<MaxReferences;i++)if(!m_References[i].Serial){free=i;break;}
 if(free==MaxReferences)return SubmissionNoCapacity;
 if(m_NextReference==(u64)-1)return SubmissionExhausted;
 TReference&ref=m_References[free];ref.Generation=s.Submission.Generation;ref.Stage=s.Serial;ref.Record=s.Submission.Slot;ref.Kind=kind;ref.Serial=++m_NextReference;
 ++r->References;out->Stage=s;out->Serial=ref.Serial;out->Slot=free;return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::ReleaseController(TUSBSubmissionReference*h){
 if(!h||h->Slot>=MaxReferences||!h->Serial)return SubmissionInvalid;
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=FindStage(h->Stage,&r);if(result!=SubmissionOK)return result;
 TReference&ref=m_References[h->Slot];
 if(ref.Serial!=h->Serial||ref.Generation!=h->Stage.Submission.Generation||ref.Stage!=h->Stage.Serial||ref.Record!=h->Stage.Submission.Slot)return SubmissionStale;
 if(!r->References)return SubmissionInvalid;
 --r->References;ref={};*h={};return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::CompleteStage(TUSBSubmissionStage s,int error){
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=FindStage(s,&r);if(result!=SubmissionOK)return result;
 if(r->State==SubmissionDispatched)return SubmissionAlready;
 if(r->StageDone)return SubmissionAlready;
 r->StageDone=TRUE;r->StageError=error;++r->CompletedStages;
 if(error&&!r->FirstError)r->FirstError=error;
 return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::RequestCancellation(TUSBSubmissionHandle h,int error){
 if(!error)return SubmissionInvalid;
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=Find(h,&r);if(result!=SubmissionOK)return result;
 if(r->State==SubmissionDispatched||r->CancelRequested)return SubmissionAlready;
 r->CancelRequested=TRUE;r->CancelError=error;return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::RequestTerminal(TUSBSubmissionHandle h,TUSBSubmissionOutcome outcome,int error){
 if(outcome<SubmissionSucceeded||outcome>SubmissionCancelled||(outcome==SubmissionSucceeded&&error))return SubmissionInvalid;
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=Find(h,&r);if(result!=SubmissionOK)return result;
 if(r->State!=SubmissionOpen)return SubmissionAlready;
 if(outcome==SubmissionSucceeded&&(!r->StageSerial||!r->StageDone||r->FirstError))return SubmissionWrongState;
 if(outcome==SubmissionCancelled&&!r->CancelRequested)return SubmissionWrongState;
 const int failure=r->FirstError?r->FirstError:error?error:outcome==SubmissionCancelled?r->CancelError:0;
 if(outcome!=SubmissionSucceeded&&!failure)return SubmissionInvalid;
 r->Outcome=outcome;r->TerminalError=outcome==SubmissionSucceeded?0:failure;r->State=SubmissionTerminalPending;return SubmissionOK;
}
TUSBSubmissionResult CUSBSubmissionPool::Dispatch(TUSBSubmissionHandle h){
 TUSBSubmissionCallback*fn;void*ctx;TUSBSubmissionSnapshot completion{};
 { // This guard MUST be destroyed before invoking a callback which may delete this pool.
  CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
  TRecord*r;auto result=Find(h,&r);if(result!=SubmissionOK)return result;
  if(r->State==SubmissionDispatched)return SubmissionAlready;
  if(r->State!=SubmissionTerminalPending)return SubmissionWrongState;
  if(r->References||(r->StageSerial&&!r->StageDone))return SubmissionReferenced;
  // A terminal success requested while references drained may not override
  // an independently reported stage failure.
  if(r->Outcome==SubmissionSucceeded&&r->FirstError)return SubmissionWrongState;
  r->State=SubmissionDispatched;CopySnapshot(*r,&completion);fn=r->Callback;ctx=r->Context;
 }
 fn(ctx,completion);
 return SubmissionOK; // no access to this, the request, or context after callback
}
TUSBSubmissionResult CUSBSubmissionPool::Reclaim(TUSBSubmissionHandle h){
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=Find(h,&r);if(result!=SubmissionOK)return result;
 if(r->State!=SubmissionDispatched||r->References)return SubmissionWrongState;
 *r={};return SubmissionOK; // metadata only; no resource is deleted
}
TUSBSubmissionResult CUSBSubmissionPool::Snapshot(TUSBSubmissionHandle h,TUSBSubmissionSnapshot*out){
 if(!out)return SubmissionInvalid;
 CTrySubmissionGate gate(&m_Gate);if(!gate.Locked())return SubmissionBusy;
 TRecord*r;auto result=Find(h,&r);if(result!=SubmissionOK)return result;
 CopySnapshot(*r,out);return SubmissionOK;
}
