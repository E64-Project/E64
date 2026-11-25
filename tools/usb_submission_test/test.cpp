#include <cassert>
#include <cstdio>
#include <atomic>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <type_traits>
#include <circle/usb/usbrequest.h>
#define private public
#include <circle/usb/usbsubmission.h>
#undef private
#include SUBMISSION_SOURCE
static unsigned checks;
#define CHECK(x) do{assert(x);checks++;}while(0)
struct Counts {unsigned count=0;TUSBSubmissionSnapshot result{};};
static void capture(void*ctx,const TUSBSubmissionSnapshot&s){auto*c=(Counts*)ctx;c->count++;c->result=s;}
static TUSBSubmissionResources resources(CUSBRequest*p){return {p,p->GetBuffer(),SubmissionCallerOwned,SubmissionCallerOwned,SubmissionCallerOwned};}
static TUSBSubmissionHandle begin(CUSBSubmissionPool&p,CUSBRequest*r,Counts*c){TUSBSubmissionHandle h{};CHECK(p.Begin(resources(r),capture,c,&h)==SubmissionOK);return h;}
static void finish(CUSBSubmissionPool&p,TUSBSubmissionHandle h){CHECK(p.RequestTerminal(h,SubmissionSucceeded,0)==SubmissionOK);CHECK(p.Dispatch(h)==SubmissionOK);CHECK(p.Reclaim(h)==SubmissionOK);}
static void deleteURB(CUSBRequest*r,void*param,void*){++*(unsigned*)param;delete r;}
static void forwardURBCallback(void*,const TUSBSubmissionSnapshot&s){s.Resources.Request->CallCompletionRoutine();}
struct DestroyContext {CUSBSubmissionPool*pool;TUSBSubmissionHandle h;unsigned*count;};
static void destroyAll(void*ctx,const TUSBSubmissionSnapshot&s){auto*d=(DestroyContext*)ctx;auto*p=d->pool;auto h=d->h;auto*count=d->count;assert(p->Dispatch(h)==SubmissionAlready);assert(p->Reclaim(h)==SubmissionOK);delete s.Resources.Request;delete p;delete d;++*count;}
int main(){
 static_assert(!std::is_copy_constructible<CUSBSubmissionPool>::value,"pool must not be copied");
 CHECK(circle_usb_submission_api_version()==1);CUSBEndpoint endpoint(EndpointTypeControl);char buffer[64]={};CUSBRequest stack(&endpoint,buffer,sizeof buffer);CUSBRequest independentRequest(&endpoint,buffer,sizeof buffer);Counts counts;CUSBSubmissionPool pool;auto h=begin(pool,&stack,&counts);TUSBSubmissionStage stage{},previous{};TUSBSubmissionReference ref{};TUSBSubmissionSnapshot snap{};
 TUSBSubmissionHandle duplicateBinding{};CHECK(pool.Begin(resources(&stack),capture,&counts,&duplicateBinding)==SubmissionAlready);
 CHECK(pool.Dispatch(h)==SubmissionWrongState);CHECK(pool.RequestTerminal(h,SubmissionSucceeded,0)==SubmissionWrongState);CHECK(pool.Reclaim(h)==SubmissionWrongState);
 // Setup/data/status complete individually; none dispatches a terminal callback.
 for(unsigned phase=0;phase<3;phase++){
  CHECK(pool.BeginStage(h,&stage)==SubmissionOK);CHECK(stage.Serial==phase+1);if(phase)CHECK(pool.CompleteStage(previous,0)==SubmissionStale);
  CHECK(pool.RetainController(stage,SubmissionChannelReference,&ref)==SubmissionOK);CHECK(pool.CompleteStage(stage,0)==SubmissionOK);CHECK(pool.CompleteStage(stage,-99)==SubmissionAlready);CHECK(counts.count==0);
  TUSBSubmissionStage next{};CHECK(pool.BeginStage(h,&next)==SubmissionReferenced);CHECK(pool.ReleaseController(&ref)==SubmissionOK);previous=stage;
 }
 CHECK(pool.Snapshot(h,&snap)==SubmissionOK&&snap.CompletedStages==3&&!snap.TerminalRequested&&snap.Resources.RequestOwner==SubmissionCallerOwned);
 CHECK(pool.RequestTerminal(h,SubmissionSucceeded,0)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK&&counts.count==1&&counts.result.TerminalCallbackDispatched&&counts.result.CompletedStages==3);CHECK(pool.Dispatch(h)==SubmissionAlready);CHECK(pool.CompleteStage(stage,0)==SubmissionAlready);CHECK(stack.GetBufLen()==sizeof buffer);CHECK(pool.Reclaim(h)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionStale);
 // Callback-owned heap URB deletes itself through its unchanged real callback.
 unsigned deleted=0;auto*heap=new CUSBRequest(&endpoint,buffer,sizeof buffer);heap->SetCompletionRoutine(deleteURB,&deleted,nullptr);TUSBSubmissionHandle heapHandle{};CHECK(pool.Begin(resources(heap),forwardURBCallback,nullptr,&heapHandle)==SubmissionOK);CHECK(pool.BeginStage(heapHandle,&stage)==SubmissionOK);CHECK(pool.CompleteStage(stage,0)==SubmissionOK);CHECK(pool.RequestTerminal(heapHandle,SubmissionSucceeded,0)==SubmissionOK);CHECK(pool.Dispatch(heapHandle)==SubmissionOK&&deleted==1);CHECK(pool.Dispatch(heapHandle)==SubmissionAlready);CHECK(pool.CompleteStage(stage,0)==SubmissionAlready);CHECK(pool.Reclaim(heapHandle)==SubmissionOK);
 // Callback deletes request, pool and context; ASan must see no post-callback access.
 auto*ownedPool=new CUSBSubmissionPool;auto*ctx=new DestroyContext{ownedPool,{},&deleted};heap=new CUSBRequest(&endpoint,buffer,sizeof buffer);auto controllerResources=resources(heap);controllerResources.RequestOwner=SubmissionControllerOwned;controllerResources.ContextOwner=SubmissionControllerOwned;
 CHECK(ownedPool->Begin(controllerResources,destroyAll,ctx,&ctx->h)==SubmissionOK);auto destructHandle=ctx->h;CHECK(ownedPool->BeginStage(destructHandle,&stage)==SubmissionOK);CHECK(ownedPool->CompleteStage(stage,0)==SubmissionOK);CHECK(ownedPool->RequestTerminal(destructHandle,SubmissionSucceeded,0)==SubmissionOK);CHECK(ownedPool->Dispatch(destructHandle)==SubmissionOK);CHECK(deleted==2);
 // Cancellation intent does not release borrowed resources or fabricate completion.
 counts={};h=begin(pool,&stack,&counts);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);TUSBSubmissionReference dma{},callbackRef{};CHECK(pool.RetainController(stage,SubmissionDMAReference,&dma)==SubmissionOK);CHECK(pool.RetainController(stage,SubmissionCompletionReference,&callbackRef)==SubmissionOK);
 CHECK(pool.RequestCancellation(h,-70)==SubmissionOK);CHECK(pool.RequestCancellation(h,-71)==SubmissionAlready);CHECK(pool.RetainController(stage,SubmissionQueueReference,&ref)==SubmissionWrongState);CHECK(pool.RequestTerminal(h,SubmissionCancelled,0)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionReferenced);CHECK(counts.count==0);CHECK(pool.CompleteStage(stage,-70)==SubmissionOK);CHECK(pool.ReleaseController(&dma)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionReferenced);CHECK(pool.ReleaseController(&callbackRef)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK);CHECK(counts.count==1&&counts.result.Outcome==SubmissionCancelled&&counts.result.CancellationError==-70);CHECK(stack.GetBufLen()==sizeof buffer);CHECK(pool.Reclaim(h)==SubmissionOK);
 // First terminal decision survives a later cancellation request.
 counts={};h=begin(pool,&stack,&counts);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);CHECK(pool.CompleteStage(stage,0)==SubmissionOK);CHECK(pool.RequestTerminal(h,SubmissionSucceeded,0)==SubmissionOK);CHECK(pool.RequestCancellation(h,-4)==SubmissionOK);CHECK(pool.RequestTerminal(h,SubmissionCancelled,-4)==SubmissionAlready);CHECK(pool.Dispatch(h)==SubmissionOK);CHECK(counts.result.Outcome==SubmissionSucceeded&&counts.result.CancellationRequested);CHECK(pool.Reclaim(h)==SubmissionOK);
 // Cancellation intent may precede a natural success; it is not a terminal result.
 h=begin(pool,&stack,&counts);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);CHECK(pool.RequestCancellation(h,-5)==SubmissionOK);CHECK(pool.CompleteStage(stage,0)==SubmissionOK);CHECK(pool.RequestTerminal(h,SubmissionSucceeded,0)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK&&counts.result.Outcome==SubmissionSucceeded&&counts.result.CancellationRequested);CHECK(pool.Reclaim(h)==SubmissionOK);
 CUSBSubmissionPool independentPool;Counts independentCounts;auto independentHandle=begin(independentPool,&independentRequest,&independentCounts);CHECK(pool.Snapshot(independentHandle,&snap)==SubmissionStale);CHECK(independentPool.RequestTerminal(independentHandle,SubmissionFailed,-3)==SubmissionOK);CHECK(independentPool.Dispatch(independentHandle)==SubmissionOK);CHECK(independentPool.Reclaim(independentHandle)==SubmissionOK);
 // Stage failure is retained; failure before any stage can be cleaned up too.
 counts={};h=begin(pool,&stack,&counts);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);CHECK(pool.CompleteStage(stage,-88)==SubmissionOK);CHECK(pool.RequestTerminal(h,SubmissionSucceeded,0)==SubmissionWrongState);CHECK(pool.RequestTerminal(h,SubmissionFailed,-99)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK&&counts.result.TerminalError==-88);CHECK(pool.Reclaim(h)==SubmissionOK);
 h=begin(pool,&stack,&counts);CHECK(pool.RequestTerminal(h,SubmissionFailed,-2)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK);CHECK(pool.Reclaim(h)==SubmissionOK);
 // Stage completion is required even when no reference is currently held.
 h=begin(pool,&stack,&counts);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);CHECK(pool.RequestCancellation(h,-9)==SubmissionOK);CHECK(pool.RequestTerminal(h,SubmissionCancelled,0)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionReferenced);CHECK(pool.CompleteStage(stage,-9)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK);CHECK(pool.Reclaim(h)==SubmissionOK);
 auto invalidResources=resources(&stack);invalidResources.RequestOwner=99;CHECK(pool.Begin(invalidResources,capture,&counts,&h)==SubmissionInvalid);CHECK(pool.Begin(resources(&stack),nullptr,&counts,&h)==SubmissionInvalid);CHECK(pool.ReleaseController(nullptr)==SubmissionInvalid);
 g_SubmissionGenerationGate=1;CHECK(pool.Begin(resources(&stack),capture,&counts,&h)==SubmissionBusy);g_SubmissionGenerationGate=0;
 // Invalid/stale tokens, overflow/underflow protection and bounded pools.
 h=begin(pool,&stack,&counts);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);CHECK(pool.CompleteStage({h,0},0)==SubmissionInvalid);CHECK(pool.RequestCancellation(h,0)==SubmissionInvalid);CHECK(pool.RetainController(stage,(TUSBSubmissionReferenceKind)99,&ref)==SubmissionInvalid);
 TUSBSubmissionReference refs[64];for(auto&r:refs){CHECK(pool.RetainController(stage,SubmissionQueueReference,&r)==SubmissionOK);}CHECK(pool.RetainController(stage,SubmissionQueueReference,&ref)==SubmissionNoCapacity);auto duplicate=refs[0];CHECK(pool.ReleaseController(&refs[0])==SubmissionOK);CHECK(pool.ReleaseController(&refs[0])==SubmissionInvalid);CHECK(pool.RetainController(stage,SubmissionQueueReference,&refs[0])==SubmissionOK);CHECK(pool.ReleaseController(&duplicate)==SubmissionStale);
 pool.m_Gate=1;auto serial=refs[0].Serial;CHECK(pool.ReleaseController(&refs[0])==SubmissionBusy&&refs[0].Serial==serial);CHECK(pool.Dispatch(h)==SubmissionBusy);pool.m_Gate=0;
 for(auto&r:refs){CHECK(pool.ReleaseController(&r)==SubmissionOK);}CHECK(pool.Snapshot(h,&snap)==SubmissionOK&&snap.ControllerReferences==0);CHECK(pool.CompleteStage(stage,0)==SubmissionOK);finish(pool,h);
 auto old=h;h=begin(pool,&stack,&counts);CHECK(h.Generation!=old.Generation);CHECK(pool.RequestCancellation(old,-1)==SubmissionStale);CHECK(pool.RequestTerminal(h,SubmissionFailed,-1)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK);CHECK(pool.Reclaim(h)==SubmissionOK);
 // Deterministic: callback starts first; late cancellation/dispatch cannot run it twice.
 struct Blocking {std::mutex m;std::condition_variable cv;bool entered=false,release=false;unsigned calls=0;} block;
 auto blocking=[](void*ctx,const TUSBSubmissionSnapshot&){auto*b=(Blocking*)ctx;std::unique_lock<std::mutex>g(b->m);b->calls++;b->entered=true;b->cv.notify_all();b->cv.wait(g,[&]{return b->release;});};
 CHECK(pool.Begin(resources(&stack),blocking,&block,&h)==SubmissionOK);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);CHECK(pool.CompleteStage(stage,0)==SubmissionOK);CHECK(pool.RequestTerminal(h,SubmissionSucceeded,0)==SubmissionOK);
 std::thread dispatch([&]{assert(pool.Dispatch(h)==SubmissionOK);});{std::unique_lock<std::mutex>g(block.m);block.cv.wait(g,[&]{return block.entered;});}CHECK(pool.RequestCancellation(h,-7)==SubmissionAlready);CHECK(pool.Dispatch(h)==SubmissionAlready);{std::lock_guard<std::mutex>g(block.m);block.release=true;}block.cv.notify_all();dispatch.join();CHECK(block.calls==1);CHECK(pool.Reclaim(h)==SubmissionOK);
 // Concurrent cancellation requests: one wins, no callback until explicit completion.
 h=begin(pool,&stack,&counts);CHECK(pool.BeginStage(h,&stage)==SubmissionOK);std::atomic<unsigned>winners{0};std::thread cancels[8];for(unsigned n=0;n<8;n++)cancels[n]=std::thread([&,n]{for(unsigned k=0;k<100000;k++){auto r=pool.RequestCancellation(h,-(int)n-100);if(r==SubmissionBusy){std::this_thread::yield();continue;}assert(r==SubmissionOK||r==SubmissionAlready);if(r==SubmissionOK)winners++;return;}assert(false);});for(auto&t:cancels){t.join();}CHECK(winners==1);CHECK(pool.Snapshot(h,&snap)==SubmissionOK&&snap.CancellationError<=-100&&snap.CancellationError>=-107);CHECK(pool.CompleteStage(stage,snap.CancellationError)==SubmissionOK);CHECK(pool.RequestTerminal(h,SubmissionCancelled,0)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK);CHECK(pool.Reclaim(h)==SubmissionOK);
 TUSBSubmissionHandle handles[16];CUSBRequest*requests[16];for(unsigned i=0;i<16;i++){requests[i]=new CUSBRequest(&endpoint,buffer,sizeof buffer);handles[i]=begin(pool,requests[i],&counts);}CHECK(pool.Begin(resources(&stack),capture,&counts,&h)==SubmissionNoCapacity);for(unsigned i=0;i<16;i++){auto v=handles[i];CHECK(pool.RequestTerminal(v,SubmissionFailed,-1)==SubmissionOK);CHECK(pool.Dispatch(v)==SubmissionOK);CHECK(pool.Reclaim(v)==SubmissionOK);delete requests[i];}
 h=begin(pool,&stack,&counts);pool.m_Records[h.Slot].StageDone=TRUE;pool.m_Records[h.Slot].StageSerial=(u64)-1;CHECK(pool.BeginStage(h,&stage)==SubmissionExhausted);pool.m_Records[h.Slot].StageSerial=0;CHECK(pool.BeginStage(h,&stage)==SubmissionOK);pool.m_NextReference=(u64)-2;CHECK(pool.RetainController(stage,SubmissionDMAReference,&ref)==SubmissionOK&&ref.Serial==(u64)-1);CHECK(pool.ReleaseController(&ref)==SubmissionOK);CHECK(pool.RetainController(stage,SubmissionDMAReference,&ref)==SubmissionExhausted);CHECK(pool.CompleteStage(stage,0)==SubmissionOK);finish(pool,h);
 g_SubmissionGeneration=(u64)-2;h=begin(pool,&stack,&counts);CHECK(h.Generation==(u64)-1);CHECK(pool.Begin(resources(&independentRequest),capture,&counts,&old)==SubmissionExhausted);CHECK(pool.RequestTerminal(h,SubmissionFailed,-1)==SubmissionOK);CHECK(pool.Dispatch(h)==SubmissionOK);CHECK(pool.Reclaim(h)==SubmissionOK);
 printf("PASS: %u production submission checks; multistage/ownership/destructive callbacks/stale tokens/cancellation/ref limits/cleanup/concurrency\n",checks);printf("host pool=%zu handle=%zu stage=%zu reference=%zu snapshot=%zu\n",sizeof(pool),sizeof(h),sizeof(stage),sizeof(ref),sizeof(snap));
}
