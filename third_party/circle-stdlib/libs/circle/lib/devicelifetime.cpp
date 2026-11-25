#include <circle/devicelifetime.h>
namespace {
// Zero-initialized POD only: no constructor or initialization-order dependency.
u32 g_DeviceLifetimeGenerationGate;
u64 g_DeviceLifetimeGeneration;
CDevice *g_DeviceLifetimeOwners[CDeviceLifetimeRegistry::MaxDevices];
class CTryGate {
 u32 *m_Gate; boolean m_Locked;
public:
 explicit CTryGate (u32 *p) : m_Gate(p), m_Locked(FALSE) {
  u32 expected=0;
  m_Locked=__atomic_compare_exchange_n(p,&expected,1,TRUE,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);
 }
 ~CTryGate () { if(m_Locked) __atomic_store_n(m_Gate,0,__ATOMIC_RELEASE); }
 boolean Locked () const { return m_Locked; }
 CTryGate(const CTryGate&)=delete;
 CTryGate&operator=(const CTryGate&)=delete;
};
}
extern "C" u32 circle_device_lifetime_api_version (void) { return 1; }
TDeviceLifetimeResult CDeviceLifetimeRegistry::Find (TDeviceLifetimeHandle h,TRecord **out) {
 if(h.nSlot>=MaxDevices || h.nGeneration==0) return LifetimeInvalid;
 TRecord &r=m_Devices[h.nSlot];
 if(r.Generation!=h.nGeneration) return LifetimeStale;
 *out=&r;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::FindReference (TDeviceLifetimeReference h,TReference **ref,TRecord **record) {
 if(h.nSlot>=MaxReferences || h.nSerial==0) return LifetimeInvalid;
 TDeviceLifetimeResult result=Find(h.Instance,record);if(result!=LifetimeOK)return result;
 TReference &r=m_References[h.nSlot];
 if(r.Serial!=h.nSerial || r.Generation!=h.Instance.nGeneration || r.DeviceSlot!=h.Instance.nSlot) return LifetimeStale;
 *ref=&r;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::RegisterPhysical (CDevice *device,TDeviceLifetimeHandle *out) {
 if(!device || !out)return LifetimeInvalid;
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 unsigned free=MaxDevices;
 for(unsigned i=0;i<MaxDevices;i++) {
  const TRecord &r=m_Devices[i];
  if(r.Generation && r.State!=LifetimeRetired && r.Device==device)return LifetimeAlreadyRegistered;
  if(free==MaxDevices && (!r.Generation || r.State==LifetimeRetired))free=i;
 }
 if(free==MaxDevices)return LifetimeNoCapacity;
 CTryGate generations(&g_DeviceLifetimeGenerationGate);if(!generations.Locked())return LifetimeBusy;
 unsigned ownerSlot=MaxDevices;
 for(unsigned i=0;i<MaxDevices;i++) {
  if(g_DeviceLifetimeOwners[i]==device)return LifetimeAlreadyRegistered;
  if(ownerSlot==MaxDevices && g_DeviceLifetimeOwners[i]==nullptr)ownerSlot=i;
 }
 if(ownerSlot==MaxDevices)return LifetimeNoCapacity;
 if(g_DeviceLifetimeGeneration==(u64)-1)return LifetimeExhausted;
 const u64 generation=++g_DeviceLifetimeGeneration;
 g_DeviceLifetimeOwners[ownerSlot]=device;
 TRecord &r=m_Devices[free];r.Generation=generation;r.Device=device;r.References=0;r.State=LifetimeInitializing;
 out->nGeneration=generation;out->nSlot=free;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::Publish (TDeviceLifetimeHandle h) {
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TRecord *r;auto result=Find(h,&r);if(result!=LifetimeOK)return result;
 if(r->State!=LifetimeInitializing)return LifetimeWrongState;
 r->State=LifetimeLive;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::MakeAlias (TDeviceLifetimeHandle h,TDeviceLifetimeHandle *out) {
 if(!out)return LifetimeInvalid;
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TRecord *r;auto result=Find(h,&r);if(result!=LifetimeOK)return result;
 if(r->State!=LifetimeInitializing && r->State!=LifetimeLive)return LifetimeWrongState;
 *out=h;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::Acquire (TDeviceLifetimeHandle h,TDeviceLifetimeReference *out) {
 if(!out)return LifetimeInvalid;
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TRecord *r;auto result=Find(h,&r);if(result!=LifetimeOK)return result;
 if(r->State!=LifetimeLive)return LifetimeWrongState;
 if(r->References>=MaxReferences)return LifetimeNoCapacity;
 unsigned free=MaxReferences;
 for(unsigned i=0;i<MaxReferences;i++)if(m_References[i].Serial==0){free=i;break;}
 if(free==MaxReferences)return LifetimeNoCapacity;
 if(m_NextReference==(u64)-1)return LifetimeExhausted;
 TReference &ref=m_References[free];ref.Generation=h.nGeneration;ref.DeviceSlot=h.nSlot;ref.Serial=++m_NextReference;
 ++r->References;out->Instance=h;out->nSerial=ref.Serial;out->nSlot=free;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::Get (TDeviceLifetimeReference h,CDevice **out) {
 if(!out)return LifetimeInvalid;
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TReference *ref;TRecord *r;auto result=FindReference(h,&ref,&r);if(result!=LifetimeOK)return result;
 // Existing references remain valid while Removing. They must be released
 // before Retire can succeed; no new references can enter in that state.
 if(!r->Device || !r->References || (r->State!=LifetimeLive && r->State!=LifetimeRemoving))return LifetimeWrongState;
 *out=r->Device;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::Release (TDeviceLifetimeReference *h) {
 if(!h)return LifetimeInvalid;
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TReference *ref;TRecord *r;auto result=FindReference(*h,&ref,&r);if(result!=LifetimeOK)return result;
 if(r->References==0)return LifetimeInvalid; // never wrap on invalid/double release
 --r->References;ref->Serial=0;ref->Generation=0;ref->DeviceSlot=0;
 *h={};return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::BeginRemoval (TDeviceLifetimeHandle h) {
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TRecord *r;auto result=Find(h,&r);if(result!=LifetimeOK)return result;
 if(r->State==LifetimeRetired)return LifetimeWrongState;
 r->State=LifetimeRemoving;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::Retire (TDeviceLifetimeHandle h,CDevice **out) {
 if(!out)return LifetimeInvalid;
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TRecord *r;auto result=Find(h,&r);if(result!=LifetimeOK)return result;
 if(r->State!=LifetimeRemoving)return LifetimeWrongState;
 if(r->References)return LifetimeReferenced;
 CTryGate generations(&g_DeviceLifetimeGenerationGate);if(!generations.Locked())return LifetimeBusy;
 unsigned ownerSlot=MaxDevices;
 for(unsigned i=0;i<MaxDevices;i++)if(g_DeviceLifetimeOwners[i]==r->Device){ownerSlot=i;break;}
 if(ownerSlot==MaxDevices)return LifetimeInvalid;
 g_DeviceLifetimeOwners[ownerSlot]=nullptr;
 *out=r->Device;r->Device=nullptr;r->State=LifetimeRetired;return LifetimeOK;
}
TDeviceLifetimeResult CDeviceLifetimeRegistry::Snapshot (TDeviceLifetimeHandle h,TDeviceLifetimeSnapshot *out) {
 if(!out)return LifetimeInvalid;
 CTryGate gate(&m_Gate);if(!gate.Locked())return LifetimeBusy;
 TRecord *r;auto result=Find(h,&r);if(result!=LifetimeOK)return result;
 out->nGeneration=r->Generation;out->nReferences=r->References;out->State=r->State;return LifetimeOK;
}
