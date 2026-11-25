#ifndef _circle_devicelifetime_h
#define _circle_devicelifetime_h
#include <circle/types.h>
class CDevice;

// Dormant metadata only. No registration, I/O, teardown or deletion hooks.
// Caller must keep the registry alive and exclusively own the right to destroy
// physical objects. Delete an object ONLY after Retire succeeds. Existing USB
// and filesystem users do not participate in this protocol in Stage 3A-1.
enum TDeviceLifetimeState { LifetimeInitializing, LifetimeLive, LifetimeRemoving, LifetimeRetired };
enum TDeviceLifetimeResult {
 LifetimeOK, LifetimeBusy, LifetimeInvalid, LifetimeStale, LifetimeWrongState,
 LifetimeNoCapacity, LifetimeExhausted, LifetimeAlreadyRegistered, LifetimeReferenced
};
struct TDeviceLifetimeHandle { u64 nGeneration; u32 nSlot; };
// A reference token denotes ONE pin; copying it does not create another pin.
// Do not use a returned device pointer after that pin is released by any copy.
struct TDeviceLifetimeReference { TDeviceLifetimeHandle Instance; u64 nSerial; u32 nSlot; };
struct TDeviceLifetimeSnapshot { u64 nGeneration; u32 nReferences; TDeviceLifetimeState State; };

class CDeviceLifetimeRegistry {
public:
 static const unsigned MaxDevices = 7;
 static const unsigned MaxReferences = 64;
 constexpr CDeviceLifetimeRegistry () : m_Gate(0), m_NextReference(0), m_Devices{}, m_References{} {}
 CDeviceLifetimeRegistry (const CDeviceLifetimeRegistry &) = delete;
 CDeviceLifetimeRegistry &operator= (const CDeviceLifetimeRegistry &) = delete;
 // Tokens are values, not pins. Partition aliases use MakeAlias, NEVER a
 // second RegisterPhysical(partitionPointer). Physical registrations are
 // globally unique by canonical pointer, with seven simultaneous owners.
 // RegisterPhysical takes the
 // canonical parent identity; it does not dereference or take ownership of it.
 TDeviceLifetimeResult RegisterPhysical (CDevice *, TDeviceLifetimeHandle *);
 TDeviceLifetimeResult Publish (TDeviceLifetimeHandle);
 TDeviceLifetimeResult MakeAlias (TDeviceLifetimeHandle, TDeviceLifetimeHandle *);
 TDeviceLifetimeResult Acquire (TDeviceLifetimeHandle, TDeviceLifetimeReference *);
 TDeviceLifetimeResult Get (TDeviceLifetimeReference, CDevice **);
 TDeviceLifetimeResult Release (TDeviceLifetimeReference *);
 TDeviceLifetimeResult BeginRemoval (TDeviceLifetimeHandle);
 TDeviceLifetimeResult Retire (TDeviceLifetimeHandle, CDevice **);
 TDeviceLifetimeResult Snapshot (TDeviceLifetimeHandle, TDeviceLifetimeSnapshot *);
 // All calls attempt locks once, returning Busy without changing metadata.
 // In particular Release(Busy) retains the reference: its owner must retain
 // and retry the token later, not discard it. No waits/callbacks/allocations.
 // Do not destroy/reset/copy a registry while registrations or users exist.
private:
 struct TRecord { u64 Generation; CDevice *Device; u32 References; TDeviceLifetimeState State; };
 struct TReference { u64 Generation, Serial; u32 DeviceSlot; };
 TDeviceLifetimeResult Find (TDeviceLifetimeHandle, TRecord **);
 TDeviceLifetimeResult FindReference (TDeviceLifetimeReference, TReference **, TRecord **);
 u32 m_Gate;
 u64 m_NextReference;
 TRecord m_Devices[MaxDevices];
 TReference m_References[MaxReferences];
};
extern "C" u32 circle_device_lifetime_api_version (void);
#endif
