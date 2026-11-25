#include <cassert>
#include <cstdio>
#include <cstring>
#include <atomic>
#include <thread>
#include <vector>
#include <condition_variable>
#include <mutex>
#include <type_traits>
// Test-only access for forced lock contention and numeric-limit injection.
#define private public
#include <circle/devicelifetime.h>
#undef private
#include LIFETIME_SOURCE
class CDevice {public:unsigned value=42;};
static unsigned checks;
#define CHECK(x) do{assert(x);checks++;}while(0)
static TDeviceLifetimeHandle live(CDeviceLifetimeRegistry&r,CDevice*d){TDeviceLifetimeHandle h{};CHECK(r.RegisterPhysical(d,&h)==LifetimeOK);CHECK(r.Publish(h)==LifetimeOK);return h;}
static void retire(CDeviceLifetimeRegistry&r,TDeviceLifetimeHandle h,CDevice*expected){CDevice*out=nullptr;CHECK(r.BeginRemoval(h)==LifetimeOK);CHECK(r.Retire(h,&out)==LifetimeOK);CHECK(out==expected);}
int main(){
 static_assert(!std::is_copy_constructible<CDeviceLifetimeRegistry>::value,"registry must not be copied");
 CHECK(circle_device_lifetime_api_version()==1);
 CDeviceLifetimeRegistry r;CDevice device,other,third;TDeviceLifetimeHandle h{},alias{},out{};TDeviceLifetimeReference ref{},second{};TDeviceLifetimeSnapshot snapshot{};CDevice*ptr=nullptr;
 CHECK(r.RegisterPhysical(nullptr,&out)==LifetimeInvalid);CHECK(r.RegisterPhysical(&device,nullptr)==LifetimeInvalid);
 CHECK(r.RegisterPhysical(&device,&h)==LifetimeOK);CHECK(h.nGeneration!=0);CHECK(r.RegisterPhysical(&device,&out)==LifetimeAlreadyRegistered);
 CHECK(r.Snapshot(h,&snapshot)==LifetimeOK&&snapshot.State==LifetimeInitializing&&snapshot.nReferences==0);
 CHECK(r.MakeAlias(h,&alias)==LifetimeOK&&alias.nGeneration==h.nGeneration&&alias.nSlot==h.nSlot);
 CHECK(r.Acquire(alias,&ref)==LifetimeWrongState);CHECK(r.Retire(h,&ptr)==LifetimeWrongState);CHECK(r.Publish(h)==LifetimeOK);CHECK(r.Publish(h)==LifetimeWrongState);
 CHECK(r.Acquire(h,&ref)==LifetimeOK);CHECK(r.Acquire(alias,&second)==LifetimeOK);CHECK(r.Get(ref,&ptr)==LifetimeOK&&ptr==&device&&ptr->value==42);
 auto duplicate=ref;CHECK(r.Release(&ref)==LifetimeOK);CHECK(r.Release(&ref)==LifetimeInvalid);CHECK(r.Release(&duplicate)==LifetimeStale);
 TDeviceLifetimeReference recycled{};CHECK(r.Acquire(h,&recycled)==LifetimeOK);CHECK(recycled.nSlot==duplicate.nSlot&&recycled.nSerial!=duplicate.nSerial);CHECK(r.Release(&duplicate)==LifetimeStale);
 auto survivor=live(r,&third);TDeviceLifetimeReference survivorRef{},extra{};CHECK(r.Acquire(survivor,&survivorRef)==LifetimeOK);
 CHECK(r.BeginRemoval(alias)==LifetimeOK);CHECK(r.Acquire(survivor,&extra)==LifetimeOK);CHECK(r.Release(&extra)==LifetimeOK);CHECK(r.BeginRemoval(h)==LifetimeOK);CHECK(r.Acquire(h,&ref)==LifetimeWrongState);CHECK(r.MakeAlias(h,&out)==LifetimeWrongState);CHECK(r.Publish(h)==LifetimeWrongState);
 CHECK(r.Retire(h,&ptr)==LifetimeReferenced);CHECK(r.Get(second,&ptr)==LifetimeOK&&ptr==&device);CHECK(r.Release(&second)==LifetimeOK);CHECK(r.Release(&recycled)==LifetimeOK);CHECK(r.Retire(h,&ptr)==LifetimeOK&&ptr==&device);CHECK(r.Retire(h,&ptr)==LifetimeWrongState);
 CHECK(r.Snapshot(h,&snapshot)==LifetimeOK&&snapshot.State==LifetimeRetired&&snapshot.nReferences==0);CHECK(r.Get(survivorRef,&ptr)==LifetimeOK&&ptr==&third);CHECK(r.Release(&survivorRef)==LifetimeOK);retire(r,survivor,&third);
 auto old=h;h=live(r,&device);CHECK(h.nSlot==old.nSlot&&h.nGeneration!=old.nGeneration);CHECK(r.Acquire(old,&ref)==LifetimeStale);CHECK(r.BeginRemoval(old)==LifetimeStale);CHECK(r.Get(duplicate,&ptr)==LifetimeStale);
 CDeviceLifetimeRegistry separate;auto independent=live(separate,&other);CHECK(independent.nGeneration!=h.nGeneration);CHECK(separate.Acquire(h,&ref)==LifetimeStale);CHECK(r.RegisterPhysical(&other,&out)==LifetimeAlreadyRegistered);
 CHECK(r.Acquire({0,0},&ref)==LifetimeInvalid);CHECK(r.Acquire({h.nGeneration,999},&ref)==LifetimeInvalid);CHECK(r.Acquire(h,nullptr)==LifetimeInvalid);CHECK(r.Release(nullptr)==LifetimeInvalid);CHECK(r.Get({},&ptr)==LifetimeInvalid);CHECK(r.Snapshot(h,nullptr)==LifetimeInvalid);
 // Busy must leave output/tokens/state intact, especially a pending release.
 CHECK(r.Acquire(h,&ref)==LifetimeOK);auto saved=ref;r.m_Gate=1;CHECK(r.Release(&ref)==LifetimeBusy);CHECK(ref.nSerial==saved.nSerial);CHECK(r.BeginRemoval(h)==LifetimeBusy);CHECK(r.Get(ref,&ptr)==LifetimeBusy);r.m_Gate=0;CHECK(r.Get(ref,&ptr)==LifetimeOK);CHECK(r.Release(&ref)==LifetimeOK);
 g_DeviceLifetimeGenerationGate=1;CHECK(r.RegisterPhysical(&third,&out)==LifetimeBusy);g_DeviceLifetimeGenerationGate=0;CHECK(r.RegisterPhysical(&third,&out)==LifetimeOK);CHECK(r.BeginRemoval(out)==LifetimeOK);g_DeviceLifetimeGenerationGate=1;CHECK(r.Retire(out,&ptr)==LifetimeBusy);g_DeviceLifetimeGenerationGate=0;CHECK(r.Snapshot(out,&snapshot)==LifetimeOK&&snapshot.State==LifetimeRemoving);CHECK(r.Retire(out,&ptr)==LifetimeOK&&ptr==&third);
 // Bounded references prevent arithmetic overflow; numeric guard also refuses
 // injected out-of-range counts rather than incrementing through UINT32_MAX.
 TDeviceLifetimeReference refs[CDeviceLifetimeRegistry::MaxReferences];
 for(auto&v:refs){CHECK(r.Acquire(h,&v)==LifetimeOK);}CHECK(r.Acquire(h,&ref)==LifetimeNoCapacity);CHECK(r.Snapshot(h,&snapshot)==LifetimeOK&&snapshot.nReferences==64);
 for(auto&v:refs){CHECK(r.Release(&v)==LifetimeOK);}CHECK(r.Snapshot(h,&snapshot)==LifetimeOK&&snapshot.nReferences==0);
 r.m_Devices[h.nSlot].References=0xffffffffU;CHECK(r.Acquire(h,&ref)==LifetimeNoCapacity);CHECK(r.m_Devices[h.nSlot].References==0xffffffffU);r.m_Devices[h.nSlot].References=0;
 CHECK(r.Acquire(h,&ref)==LifetimeOK);r.m_Devices[h.nSlot].References=0;CHECK(r.Release(&ref)==LifetimeInvalid);r.m_Devices[h.nSlot].References=1;CHECK(r.Release(&ref)==LifetimeOK);
 // Deterministic order: acquisition wins, removal cannot retire until release.
 std::mutex m;std::condition_variable cv;int phase=0;
 std::thread holder([&]{TDeviceLifetimeReference v{};assert(r.Acquire(h,&v)==LifetimeOK);{std::lock_guard<std::mutex>g(m);phase=1;}cv.notify_all();{std::unique_lock<std::mutex>g(m);cv.wait(g,[&]{return phase==2;});}assert(r.Get(v,&ptr)==LifetimeOK);assert(r.Release(&v)==LifetimeOK);});
 {std::unique_lock<std::mutex>g(m);cv.wait(g,[&]{return phase==1;});}CHECK(r.BeginRemoval(h)==LifetimeOK);CHECK(r.Retire(h,&ptr)==LifetimeReferenced);{std::lock_guard<std::mutex>g(m);phase=2;}cv.notify_all();holder.join();CHECK(r.Retire(h,&ptr)==LifetimeOK);
 // Deterministic reverse order, then native races with a bounded test retry.
 h=live(r,&device);CHECK(r.BeginRemoval(h)==LifetimeOK);std::thread rejected([&]{TDeviceLifetimeReference v{};assert(r.Acquire(h,&v)==LifetimeWrongState);});rejected.join();CHECK(r.Retire(h,&ptr)==LifetimeOK);
 for(unsigned n=0;n<300;n++){
  h=live(r,&device);std::atomic<unsigned>ready{0};std::atomic<bool>go{false};TDeviceLifetimeResult acquired=LifetimeInvalid,removed=LifetimeInvalid;TDeviceLifetimeReference v{};
  std::thread a([&]{ready++;while(!go.load())std::this_thread::yield();for(unsigned i=0;i<100000;i++){acquired=r.Acquire(h,&v);if(acquired!=LifetimeBusy)return;std::this_thread::yield();}assert(false);});
  std::thread b([&]{ready++;while(!go.load())std::this_thread::yield();for(unsigned i=0;i<100000;i++){removed=r.BeginRemoval(h);if(removed!=LifetimeBusy)return;std::this_thread::yield();}assert(false);});
  while(ready!=2){std::this_thread::yield();}go=true;a.join();b.join();CHECK(removed==LifetimeOK);CHECK(acquired==LifetimeOK||acquired==LifetimeWrongState);
  if(acquired==LifetimeOK){CHECK(r.Retire(h,&ptr)==LifetimeReferenced);CHECK(r.Release(&v)==LifetimeOK);}CHECK(r.Retire(h,&ptr)==LifetimeOK);CHECK(r.Acquire(h,&v)==LifetimeWrongState);
 }
 // Independent registry progress while another registry's gate is unavailable.
 r.m_Gate=1;CHECK(separate.Acquire(independent,&ref)==LifetimeOK);CHECK(separate.Release(&ref)==LifetimeOK);r.m_Gate=0;retire(separate,independent,&other);
 CDevice *heap=new CDevice;auto heapHandle=live(r,heap);CHECK(r.Acquire(heapHandle,&ref)==LifetimeOK);auto staleHeapRef=ref;CHECK(r.BeginRemoval(heapHandle)==LifetimeOK);CHECK(r.Retire(heapHandle,&ptr)==LifetimeReferenced);CHECK(r.Get(ref,&ptr)==LifetimeOK&&ptr==heap&&ptr->value==42);CHECK(r.Release(&ref)==LifetimeOK);CHECK(r.Retire(heapHandle,&ptr)==LifetimeOK&&ptr==heap);delete ptr;CHECK(r.Get(staleHeapRef,&ptr)==LifetimeStale);CHECK(r.Acquire(heapHandle,&ref)==LifetimeWrongState);
 CDevice devices[8];TDeviceLifetimeHandle handles[7];for(unsigned i=0;i<7;i++)handles[i]=live(r,&devices[i]);CHECK(r.RegisterPhysical(&devices[7],&out)==LifetimeNoCapacity);for(unsigned i=0;i<7;i++)retire(r,handles[i],&devices[i]);
 // Reference serial exhaustion cannot produce an ABA token.
 h=live(r,&device);r.m_NextReference=(u64)-2;CHECK(r.Acquire(h,&ref)==LifetimeOK&&ref.nSerial==(u64)-1);CHECK(r.Release(&ref)==LifetimeOK);CHECK(r.Acquire(h,&ref)==LifetimeExhausted);retire(r,h,&device);
 // Global generations never wrap, even across independent registry objects.
 g_DeviceLifetimeGeneration=(u64)-2;CHECK(r.RegisterPhysical(&device,&h)==LifetimeOK&&h.nGeneration==(u64)-1);CHECK(separate.RegisterPhysical(&other,&out)==LifetimeExhausted);retire(r,h,&device);
 printf("PASS: %u checks including 300 acquire/removal races, deterministic schedules, stale/copy/wrong-registry tokens, alias identity, limits, Busy release and generation exhaustion\n",checks);
 printf("host registry bytes=%zu, handle=%zu, reference=%zu; no production registry instance or device hooks\n",sizeof(r),sizeof(h),sizeof(ref));
}
