#ifndef _circle_usb_usbsubmission_h
#define _circle_usb_usbsubmission_h
#include <circle/types.h>
class CUSBRequest;
// Dormant ledger only: never submits, cancels, frees, or dereferences a URB.
// Use one pool for a URB ownership domain; a URB must not be registered
// simultaneously in multiple pools. Duplicate bindings inside a pool are rejected.
// All resources and the pool remain externally owned. Ownership labels do
// not transfer ownership. Future integration must account for every producer.
enum TUSBSubmissionResult { SubmissionOK, SubmissionBusy, SubmissionInvalid, SubmissionStale,
 SubmissionWrongState, SubmissionAlready, SubmissionNoCapacity, SubmissionExhausted, SubmissionReferenced };
enum TUSBResourceOwner : u32 { SubmissionCallerOwned, SubmissionControllerOwned };
enum TUSBSubmissionOutcome : u32 { SubmissionNoOutcome, SubmissionSucceeded, SubmissionFailed, SubmissionCancelled };
enum TUSBSubmissionState : u32 { SubmissionFree, SubmissionOpen, SubmissionTerminalPending, SubmissionDispatched };
enum TUSBSubmissionReferenceKind : u32 { SubmissionQueueReference, SubmissionChannelReference, SubmissionDMAReference, SubmissionCompletionReference };
struct TUSBSubmissionHandle { u64 Generation; u32 Slot; };
struct TUSBSubmissionStage { TUSBSubmissionHandle Submission; u64 Serial; };
struct TUSBSubmissionReference { TUSBSubmissionStage Stage; u64 Serial; u32 Slot; };
struct TUSBSubmissionResources {
 CUSBRequest *Request; void *Buffer;
 u32 RequestOwner, BufferOwner, ContextOwner;
};
struct TUSBSubmissionSnapshot {
 TUSBSubmissionState State;
 TUSBSubmissionOutcome Outcome;
 TUSBSubmissionResources Resources;
 u64 StageSerial, CompletedStages;
 u32 ControllerReferences;
 boolean StageCompleted, CancellationRequested, TerminalRequested, TerminalCallbackDispatched;
 int StageError, FirstError, CancellationError, TerminalError;
};
typedef void TUSBSubmissionCallback (void *, const TUSBSubmissionSnapshot &);
class CUSBSubmissionPool {
public:
 static const unsigned MaxSubmissions=16, MaxReferences=64;
 constexpr CUSBSubmissionPool () : m_Gate(0), m_NextReference(0), m_Records{}, m_References{} {}
 CUSBSubmissionPool(const CUSBSubmissionPool&)=delete;
 CUSBSubmissionPool&operator=(const CUSBSubmissionPool&)=delete;
 TUSBSubmissionResult Begin(TUSBSubmissionResources,TUSBSubmissionCallback*,void*,TUSBSubmissionHandle*);
 TUSBSubmissionResult BeginStage(TUSBSubmissionHandle,TUSBSubmissionStage*);
 TUSBSubmissionResult RetainController(TUSBSubmissionStage,TUSBSubmissionReferenceKind,TUSBSubmissionReference*);
 TUSBSubmissionResult ReleaseController(TUSBSubmissionReference*);
 TUSBSubmissionResult CompleteStage(TUSBSubmissionStage,int error);
 // Cancellation is intent only: it does not finish a stage or choose the
 // terminal outcome. A natural success may win a cancellation race.
 TUSBSubmissionResult RequestCancellation(TUSBSubmissionHandle,int error);
 TUSBSubmissionResult RequestTerminal(TUSBSubmissionHandle,TUSBSubmissionOutcome,int error);
 TUSBSubmissionResult Dispatch(TUSBSubmissionHandle);
 TUSBSubmissionResult Reclaim(TUSBSubmissionHandle);
 TUSBSubmissionResult Snapshot(TUSBSubmissionHandle,TUSBSubmissionSnapshot*);
 // Busy never mutates metadata: retain pending reference tokens and retry
 // later. The pool must outlive every API caller and retained controller ref.
 // Dispatch publishes "dispatched" before calling out, not "callback returned".
 // It never touches this pool or URB after invoking the callback, so the
 // callback's sole owner may destroy them. Other callers must not keep using
 // that destroyed pool. Never infer hardware/DMA quiescence from untracked refs.
private:
 struct TRecord {
  u64 Generation, StageSerial, CompletedStages;
  TUSBSubmissionState State;
  u32 References;
  boolean StageDone, CancelRequested;
  int StageError, FirstError, CancelError, TerminalError;
  TUSBSubmissionOutcome Outcome;
  TUSBSubmissionResources Resources;
  TUSBSubmissionCallback *Callback;void *Context;
 };
 struct TReference { u64 Generation, Stage, Serial; u32 Record, Kind; };
 TUSBSubmissionResult Find(TUSBSubmissionHandle,TRecord**);
 TUSBSubmissionResult FindStage(TUSBSubmissionStage,TRecord**);
 static void CopySnapshot(const TRecord&,TUSBSubmissionSnapshot*);
 u32 m_Gate;u64 m_NextReference;
 TRecord m_Records[MaxSubmissions];
 TReference m_References[MaxReferences];
};
extern "C" u32 circle_usb_submission_api_version(void);
#endif
