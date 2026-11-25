#include <circle/usb/usbserialft231x.h>
#include <circle/usb/usbhostcontroller.h>
#include <circle/devicenameservice.h>
#include <circle/timer.h>
#include "rs232drv/rs232usb.h"
#include <cassert>
#include <cstdio>

static void tick(){CTimer::now+=100000;e64_rs232_usb_service();}
static CUSBSerialDevice *serial(unsigned n=1){return static_cast<CUSBSerialDevice*>(CDeviceNameService::Get()->GetDevice("utty",n,false));}
static void packet_status_api(){
 CUSBDevice device;CUSBHostController host;CUSBFunction parent(&device,&host);
 CUSBSerialFT231XDevice driver(&parent);assert(driver.Configure());assert(driver.EnableAsyncIO());
 uint8_t bytes[64]{};TUSBSerialPacketStatus status{};
 auto stale=[&](){status={true,0xff,0xff};};
 auto invalid=[&](){assert(!status.HeaderValid&&!status.ModemStatus&&!status.LineStatus);};
 for(unsigned flags:{0u,0x02u,0x04u,0x08u,0x10u,0x1eu}){
  assert(driver.SubmitSerialPacket(true,nullptr,64)==1);
  stale();assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==-2);invalid();
  host.Finish({0xa5,(uint8_t)(0x60|flags),0,0x55,0xaa,0xff});
  assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==4);
  assert(status.HeaderValid&&status.ModemStatus==0xa5&&status.LineStatus==(0x60|flags));
  assert(bytes[0]==0&&bytes[1]==0x55&&bytes[2]==0xaa&&bytes[3]==0xff);
  assert(driver.SubmitSerialPacket(true,nullptr,64)==1);host.Finish({0x12,(uint8_t)flags});
  assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==0);
  assert(status.HeaderValid&&status.ModemStatus==0x12&&status.LineStatus==flags);
 }
 // Every non-header result clears a reused caller-owned status object.
 stale();assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==-1);invalid();
 assert(driver.SubmitSerialPacket(true,nullptr,64)==1);host.Finish({});
 stale();assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==0);invalid();
 assert(driver.SubmitSerialPacket(true,nullptr,64)==1);host.Finish({},false);
 stale();assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==-1);invalid();
 assert(driver.SubmitSerialPacket(true,nullptr,64)==1);host.Finish({0xff});
 stale();assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==-1);invalid();
 assert(driver.SubmitSerialPacket(false,bytes,4)==1);host.Finish({},true,4);
 stale();assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==4);invalid();
 // Original API still consumes exactly one completion and strips the header.
 assert(driver.SubmitSerialPacket(true,nullptr,64)==1);host.Finish({0x10,0x7e,0x81,0x42});
 assert(driver.PollSerialPacket(bytes,64)==2&&bytes[0]==0x81&&bytes[1]==0x42);
 stale();assert(driver.PollSerialPacketWithStatus(bytes,64,&status)==-1);invalid();
}
static void hardware_framing_regression(){
 CUSBDevice device;CUSBHostController host;CUSBFunction parent(&device,&host);
 auto *driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());
 unsigned oldParity=0,oldBits=8,oldStops=1;uint8_t byte=0;
 const unsigned parityEncoding[]={0x000,0x200,0x100}; // FTDI wire encoding, not Circle enum order.
 const unsigned rates[]={300,600,1200,2400},divisors[]={10000,5000,2500,1250};
 e64_rs232_usb_status_t state{};
 for(unsigned parity=0;parity<3;++parity)for(unsigned bits:{7u,8u})for(unsigned stops:{1u,2u})
 for(unsigned r=0;r<4;++r){
  bool changed=parity!=oldParity||bits!=oldBits||stops!=oldStops;
  unsigned begin=host.controls.size();bool pending=host.pending!=nullptr;
  assert(!e64_rs232_usb_open_configured(1,rates[r],parity,bits,stops));
  tick();if(pending){assert(host.controls.size()==begin);host.Finish({0x10,0x7e,0x99});tick();}
  unsigned cursor=begin;
  auto control=[&](unsigned request,unsigned value){assert(cursor<host.controls.size());
   auto c=host.controls[cursor++];assert(c[0]==request&&c[1]==value&&c[2]==0);};
  if(changed){control(0,1);control(0,2);}
  control(3,divisors[r]);control(4,bits|parityEncoding[parity]|(stops==2?0x1000:0));
  if(changed)control(0,1);
  assert(cursor==host.controls.size()&&host.pending);
  e64_rs232_usb_status(&state);assert(state.ready&&state.baud==rates[r]);
  assert(state.parity==parity&&state.dataBits==bits&&state.stopBits==stops);
  auto base=state;
  // Repeated settings are a true no-op, including epoch and USB controls.
  assert(!e64_rs232_usb_set_framing(parity,bits,stops));tick();e64_rs232_usb_status(&state);
  assert(state.epoch==base.epoch&&host.controls.size()==cursor);
  assert(e64_rs232_usb_set_framing(3,bits,stops)==-1);
  assert(e64_rs232_usb_set_framing(parity,6,stops)==-1);
  assert(e64_rs232_usb_set_framing(parity,bits,0)==-1);
  e64_rs232_usb_status(&state);assert(state.epoch==base.epoch&&state.ready);
  // No status-based discard, even under non-default framing.
  host.Finish({0x10,0x7e,0x00,0x55,0x7f});tick();
  for(auto value:{0,0x55,0x7f})assert(e64_rs232_usb_get(&byte)==1&&byte==value);
  assert(!e64_rs232_usb_get(&byte));e64_rs232_usb_status(&state);
  assert(state.rxStatusObservations==base.rxStatusObservations+1);
  assert(state.rxParityObservations==base.rxParityObservations+1);
  assert(state.rxFramingObservations==base.rxFramingObservations+1);
  assert(state.rxOverrunObservations==base.rxOverrunObservations+1);
  assert(state.rxBreakObservations==base.rxBreakObservations+1);
  oldParity=parity;oldBits=bits;oldStops=stops;
 }
 // The fixture can fail all controls; it cannot fail just the second purge
 // or the post-configuration purge without changing an unauthorized fixture.
 unsigned begin=host.controls.size();auto base=state;
 assert(!e64_rs232_usb_set_framing(0,8,1));host.controlsOK=false;
 host.Finish({0x10,0x60});tick();e64_rs232_usb_status(&state);
 assert(!state.ready&&!host.pending&&state.errors==base.errors+1);
 assert(host.controls.size()==begin+1&&host.controls.back()[0]==0&&host.controls.back()[1]==1);
 tick();assert(host.controls.size()==begin+1); // Fault remains latched.
 host.controlsOK=true;assert(!e64_rs232_usb_open(1,2400));tick();
 e64_rs232_usb_status(&state);assert(state.ready&&state.parity==0&&state.dataBits==8&&state.stopBits==1);
 // With unchanged 8N1 there must be no purge; fail the baud control itself.
 begin=host.controls.size();base=state;assert(!e64_rs232_usb_open(1,2400));host.controlsOK=false;
 host.Finish({0x10,0x60});tick();e64_rs232_usb_status(&state);
 assert(!state.ready&&!host.pending&&state.errors==base.errors+1);
 assert(host.controls.size()==begin+1&&host.controls.back()[0]==3);
 host.controlsOK=true;assert(!e64_rs232_usb_open_configured(1,2400,1,7,2));tick();
 e64_rs232_usb_status(&state);assert(state.ready);
 delete driver;host.Finish({},false);tick();
 driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());tick();
 e64_rs232_usb_status(&state);assert(state.ready&&state.parity==1&&state.dataBits==7&&state.stopBits==2);
 assert(host.controls.back()[0]==0&&host.controls.back()[1]==1); // Reapplied non-default framing.
 host.Finish({0x10,0x60,0x55});tick();assert(e64_rs232_usb_get(&byte)==1&&byte==0x55);
 delete driver;host.Finish({},false);e64_rs232_usb_close();tick();
}
// Real Circle serial instances register their own utty numbers. Each fixture
// controller owns its device's requests; no synthetic discovery result is used.
struct DiscoveryDevice {
 CUSBDevice usb;CUSBHostController host;CUSBFunction parent;
 CUSBSerialFT231XDevice *driver;
 DiscoveryDevice(unsigned vendor=0x0403,unsigned product=0x6001):parent(&usb,&host){
  usb.descriptor.idVendor=vendor;usb.descriptor.idProduct=product;
  driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());
 }
 ~DiscoveryDevice(){delete driver;if(host.pending)host.Finish({},false);}
};
static e64_rs232_usb_discovery_t discovery(){
 e64_rs232_usb_discovery_t result{};e64_rs232_usb_discovery(&result);return result;
}
static e64_rs232_usb_status_t usb_state(){
 e64_rs232_usb_status_t result{};e64_rs232_usb_status(&result);return result;
}
static void observations_equal(const e64_rs232_usb_status_t &a,const e64_rs232_usb_status_t &b){
 assert(a.rxStatusObservations==b.rxStatusObservations&&a.rxOverrunObservations==b.rxOverrunObservations);
 assert(a.rxParityObservations==b.rxParityObservations&&a.rxFramingObservations==b.rxFramingObservations&&a.rxBreakObservations==b.rxBreakObservations);
}
static void automatic_discovery_regression(){
 DiscoveryDevice *devices[16]{};uint8_t byte=0;
 auto pump=[&](unsigned count){for(unsigned pass=0;pass<count;++pass){
  for(auto *d:devices)if(d&&d->host.pending)d->host.Finish({0x10,0x60});
  tick();
 }};
 assert(!e64_rs232_usb_select(E64_RS232_USB_AUTO));
 assert(!e64_rs232_usb_open_configured(17,2400,1,7,2));tick();
 auto absent=discovery();assert(absent.requested==17&&!absent.resolved&&!absent.compatibleMask&&!absent.ready);
 assert(e64_rs232_usb_put(1)==-1&&!e64_rs232_usb_get(&byte));
 e64_rs232_usb_close();tick();assert(discovery().requested==17);
 // Register devices before opening the guest session: startup-style inventory.
 // Wrong VID and wrong PID occupy positions 1/2; position 16 is compatible.
 for(unsigned i=0;i<16;++i){devices[i]=new DiscoveryDevice(i==0?0x1234:0x0403,i==15?0x6001:0x6015);
  assert(serial(i+1)&&serial(i+1)->GetHostDevice()==devices[i]->driver);
 }
 // Independently test vendor rejection with an otherwise correct product.
 devices[0]->usb.descriptor.idProduct=0x6001;
 for(unsigned i=2;i<15;++i){delete devices[i];devices[i]=nullptr;}
 tick();auto d=discovery();assert(d.requested==17&&d.resolved==16&&d.compatibleMask==0x8000&&!d.ready);
 assert(!devices[15]->host.pending); // Presence does not configure a closed session.
 assert(!e64_rs232_usb_open_configured(17,2400,1,7,2));tick();assert(discovery().ready);
 auto *high=devices[15];assert(high->host.pending);
 high->host.Finish({0x10,0x7e,0x00,0x55,0x7f});tick();
 auto stable=usb_state();assert(stable.rxQueued==3);assert(!e64_rs232_usb_put(0xa5));
 stable=usb_state();unsigned controls=high->host.controls.size();auto *pending=high->host.pending;
 for(int i=0;i<8;++i)tick();
 auto after=usb_state();assert(after.epoch==stable.epoch&&after.rxQueued==3&&after.txQueued==1);
 assert(high->host.controls.size()==controls&&high->host.pending==pending);observations_equal(stable,after);
 for(int i=0;i<100;++i){auto cached=discovery();assert(cached.requested==17&&cached.resolved==16&&cached.ready);}
 assert(high->host.controls.size()==controls&&high->host.pending==pending&&usb_state().epoch==stable.epoch);
 // A newly compatible utty1 supersedes utty16 while its IN remains pending.
 delete devices[0];devices[0]=new DiscoveryDevice();assert(serial(1)->GetHostDevice()==devices[0]->driver);
 tick();d=discovery();assert(d.resolved==1&&d.compatibleMask==0x8001&&!d.ready);
 after=usb_state();assert(after.epoch!=stable.epoch&&!after.rxQueued&&!after.txQueued);
 high->host.Finish({0x10,0x7e,0x99});tick();tick();tick();
 assert(discovery().ready&&devices[0]->host.pending&&!high->host.pending);
 assert(!e64_rs232_usb_get(&byte));observations_equal(stable,usb_state());
 assert(usb_state().baud==2400&&usb_state().parity==1&&usb_state().dataBits==7&&usb_state().stopBits==2);
 devices[0]->host.Finish({0x10,0x7e,0x55});tick();
 assert(e64_rs232_usb_get(&byte)==1&&byte==0x55); // Flagged data is retained.
 // Remove selected utty1 with OUT pending; late completion cannot be replayed.
 assert(!e64_rs232_usb_put(0x42));devices[0]->host.Finish({0x10,0x60});tick();
 assert(devices[0]->host.pending->GetBufLen()==1);
 auto beforeRemoval=usb_state();auto *retiredOut=devices[0];
 delete retiredOut->driver;retiredOut->driver=nullptr;devices[0]=nullptr;tick();
 assert(discovery().resolved==16&&discovery().ready&&high->host.pending->GetBufLen()==64);
 retiredOut->host.Finish({},true,1);delete retiredOut;tick();
 assert(high->host.pending->GetBufLen()==64&&!usb_state().txQueued);
 observations_equal(beforeRemoval,usb_state());
 // Lower-index handover with OUT pending on the still-connected old adapter.
 assert(!e64_rs232_usb_put(0x66));high->host.Finish({0x10,0x60});tick();
 assert(high->host.pending->GetBufLen()==1);
 devices[0]=new DiscoveryDevice();tick();assert(!discovery().ready&&discovery().resolved==1);
 high->host.Finish({},true,1);tick();tick();tick();
 assert(discovery().ready&&devices[0]->host.pending->GetBufLen()==64&&!high->host.pending);
 assert(!usb_state().txQueued); // Old OUT was neither queued nor replayed.
 // Same-index replacement exercises removal callbacks, not pointer equality.
 stable=usb_state();auto *retiredIn=devices[0];
 delete retiredIn->driver;retiredIn->driver=nullptr;devices[0]=new DiscoveryDevice();tick();
 assert(discovery().resolved==1&&discovery().ready&&usb_state().epoch!=stable.epoch);
 retiredIn->host.Finish({0x10,0x7e,0xcc});delete retiredIn;tick();
 assert(!e64_rs232_usb_get(&byte));
 observations_equal(stable,usb_state());
 assert(usb_state().baud==2400&&usb_state().parity==1&&usb_state().dataBits==7&&usb_state().stopBits==2);
 // Replace again, but fail configuration. Detected must remain separate from ready.
 delete devices[0];devices[0]=new DiscoveryDevice();devices[0]->host.controlsOK=false;tick();
 d=discovery();assert(d.resolved==1&&d.compatibleMask==0x8001&&!d.ready);
 stable=usb_state();controls=devices[0]->host.controls.size();
 for(int i=0;i<8;++i)tick();
 assert(usb_state().epoch==stable.epoch&&usb_state().errors==stable.errors);
 assert(devices[0]->host.controls.size()==controls);observations_equal(stable,usb_state());
 devices[0]->host.controlsOK=true;assert(!e64_rs232_usb_open_configured(17,2400,1,7,2));tick();assert(discovery().ready);
 // Auto passes every supported baud/framing tuple to the actual FTDI driver.
 const unsigned rates[]={300,600,1200,2400},divisors[]={10000,5000,2500,1250};
 const unsigned parityEncoding[]={0,0x200,0x100};
 for(unsigned r=0;r<4;++r)for(unsigned parity=0;parity<3;++parity)
 for(unsigned bits:{7u,8u})for(unsigned stops:{1u,2u}){
  unsigned begin=devices[0]->host.controls.size();
  assert(!e64_rs232_usb_open_configured(17,rates[r],parity,bits,stops));pump(2);
  auto state=usb_state();assert(discovery().ready&&discovery().resolved==1);
  assert(state.baud==rates[r]&&state.parity==parity&&state.dataBits==bits&&state.stopBits==stops);
  bool sawBaud=false,sawLine=false;
  for(unsigned i=begin;i<devices[0]->host.controls.size();++i){auto c=devices[0]->host.controls[i];
   if(c[0]==3){assert(c[1]==divisors[r]);sawBaud=true;}
   if(c[0]==4){assert(c[1]==(bits|parityEncoding[parity]|(stops==2?0x1000:0)));sawLine=true;}
  }
  assert(sawBaud&&sawLine);
  devices[0]->host.Finish({0x10,0x7e,0x00,0x55,0x7f});tick();
  for(auto value:{0,0x55,0x7f})assert(e64_rs232_usb_get(&byte)==1&&byte==value);
  assert(usb_state().rxParityObservations==state.rxParityObservations+1);
 }
 // Every manual selection resolves only its requested position, despite Auto
 // having two candidates. Positions 2..15 must never silently fall back.
 for(unsigned index=1;index<=16;++index){
  assert(!e64_rs232_usb_select(index));assert(!e64_rs232_usb_open_configured(index,1200,2,8,2));pump(6);
  d=discovery();assert(d.requested==index&&d.resolved==((index==1||index==16)?index:0));
  assert(d.ready==(index==1||index==16));
  auto state=usb_state();assert(state.baud==1200&&state.parity==2&&state.dataBits==8&&state.stopBits==2);
 }
 assert(!e64_rs232_usb_select(17));assert(!e64_rs232_usb_open(17,2400));pump(6);
 stable=usb_state();assert(discovery().resolved==1&&discovery().ready&&stable.parity==0&&stable.dataBits==8&&stable.stopBits==1);
 assert(e64_rs232_usb_select(18)==-1&&e64_rs232_usb_open(18,2400)==-1);
 assert(discovery().requested==17&&usb_state().epoch==stable.epoch);
 e64_rs232_usb_close();pump(6);d=discovery();assert(d.requested==17&&d.resolved==1&&!d.ready&&d.compatibleMask==0x8001);
 // Idle/closed-session removal remains visible after the removal handler retires.
 delete devices[0];devices[0]=nullptr;tick();assert(discovery().resolved==16&&!discovery().ready);
 assert(!e64_rs232_usb_select(0));tick();assert(!discovery().requested&&!discovery().resolved&&discovery().compatibleMask==0x8000);
 for(auto *device:devices)delete device;
 tick();assert(!discovery().compatibleMask);
 // First compatible insertion into an already open, empty Auto session.
 assert(!e64_rs232_usb_select(17));assert(!e64_rs232_usb_open(17,2400));tick();
 assert(!discovery().resolved&&!discovery().ready);
 auto *late=new DiscoveryDevice();tick();assert(discovery().resolved==1&&discovery().ready);
 late->host.Finish({0x10,0x60,0x00,0xff});tick();
 assert(e64_rs232_usb_get(&byte)==1&&byte==0x00&&e64_rs232_usb_get(&byte)==1&&byte==0xff);
 delete late;tick();assert(discovery().requested==17&&!discovery().resolved&&!discovery().ready);
 e64_rs232_usb_close();assert(!e64_rs232_usb_select(0));tick();
}
int main(){
 packet_status_api();
 CUSBDevice device;CUSBHostController host;CUSBFunction parent(&device,&host);
 assert(!e64_rs232_usb_open(1,300));tick();
 e64_rs232_usb_status_t absent{};e64_rs232_usb_status(&absent);
 assert(!absent.ready&&host.controls.empty()&&!host.pending);
 puts("PASS scenario 1: select Physical FTDI while disconnected");
 auto *inserted=new CUSBSerialFT231XDevice(&parent);assert(inserted->Configure());tick();
 assert(host.pending);e64_rs232_usb_status(&absent);assert(absent.ready);
 puts("PASS scenario 2: insert FTDI after backend selected (host simulation)");
 delete inserted;host.Finish({},false);e64_rs232_usb_close();tick();
 auto *driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());assert(serial());
 auto *id=driver->GetDeviceIDTable();assert(id[0].vendor==0x0403&&id[0].product==0x6001);
 unsigned initial=host.controls.size();tick();assert(host.controls.size()==initial&&!host.pending); // Off by default.
 puts("PASS scenario 4: insert FTDI while Physical FTDI disabled (host simulation)");
 assert(!e64_rs232_usb_open(1,300));tick();assert(host.pending);
 puts("PASS scenario 3: select Physical FTDI after insertion (host simulation)");
 bool baud=false,framing=false;
 for(unsigned i=initial;i<host.controls.size();++i){auto c=host.controls[i];if(c[0]==3){assert(c[1]==10000&&c[2]==0);baud=true;}if(c[0]==4){assert(c[1]==8);framing=true;}}
 assert(baud&&framing);e64_rs232_usb_status_t status{};e64_rs232_usb_status(&status);assert(status.ready&&status.baud==300);assert(((uintptr_t)host.pending->GetBuffer()&63)==0);host.Finish({0x10,0x60,0,0x55,0xaa,0xff});tick();
 uint8_t b;for(auto want:{0,0x55,0xaa,0xff}){assert(e64_rs232_usb_get(&b)==1&&b==want);}assert(e64_rs232_usb_get(&b)==0);
 for(auto value:{0,0x55,0xaa,0xff})assert(!e64_rs232_usb_put(value));
 host.Finish({0x10,0x60});tick();assert(host.pending&&host.pending->GetBufLen()==4);
 auto *out=static_cast<uint8_t*>(host.pending->GetBuffer());assert(out[0]==0&&out[1]==0x55&&out[2]==0xaa&&out[3]==0xff);
 host.Finish({},true,4);tick();assert(host.pending); // RX again, never concurrent split transactions.
 assert(!e64_rs232_usb_set_baud(1200));unsigned before=host.controls.size();tick();assert(host.controls.size()==before); // Wait for existing IN.
 host.Finish({0x10,0x60,0x99});tick();assert(e64_rs232_usb_get(&b)==0); // Old epoch discarded.
 assert(host.controls[before][0]==3&&host.controls[before][1]==2500);
 for(unsigned rate:{600u,2400u,300u,1200u}) {
  assert(!e64_rs232_usb_set_baud(rate));before=host.controls.size();
  tick();assert(host.controls.size()==before);
  host.Finish({0,0,0x99});tick();assert(e64_rs232_usb_get(&b)==0);
  assert(host.controls[before][0]==3&&host.controls[before][1]==3000000/rate);
  e64_rs232_usb_status(&status);assert(status.ready&&status.baud==rate);
 }
 // Pending request retains its DMA buffer and endpoints across driver destruction.
 auto *pending=host.pending;assert(pending);delete driver;assert(!serial());assert(e64_rs232_usb_put(1)==-1);
 pending->SetStatus(0);host.Finish({},false);tick();assert(e64_rs232_usb_get(&b)==0);
 driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());tick();assert(host.pending);
 assert(!e64_rs232_usb_put(0x66));host.Finish({0,0,0x22});tick();assert(e64_rs232_usb_get(&b)==1&&b==0x22);
 assert(host.pending&&host.pending->GetBufLen()==1); // Unplug active OUT too.
 delete driver;host.Finish({},false);tick();assert(e64_rs232_usb_get(&b)==0);
 driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());tick();assert(host.pending);
 // Abandoned queued request is deleted without completion by Circle unplug.
 host.Abandon();delete driver;tick();assert(e64_rs232_usb_get(&b)==0);
 // Wrong PID at the explicitly selected utty index must never be claimed.
 device.descriptor.idProduct=0x6015;driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());
 before=host.controls.size();tick();assert(host.controls.size()==before&&!host.pending);delete driver;
 device.descriptor.idProduct=0x6001;driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());
 // Selection is by utty index, not "first attached FTDI".
 assert(!e64_rs232_usb_open(2,300));tick();assert(!host.pending);
 assert(!e64_rs232_usb_open(1,300));tick();assert(host.pending);
 host.Finish({0});tick();assert(e64_rs232_usb_get(&b)==0&&!host.pending); // Malformed FTDI header faults safely.
 e64_rs232_usb_close();tick();delete driver;
 // Production adapter decoding and observation counts at the proven 2400/8N1
 // format. Flagged payload remains deliverable; no discard policy is enabled.
 driver=new CUSBSerialFT231XDevice(&parent);assert(driver->Configure());
 assert(!e64_rs232_usb_open(1,2400));before=host.controls.size();tick();
 bool baud2400=false,format8n1=false;
 for(unsigned i=before;i<host.controls.size();++i){auto c=host.controls[i];
  if(c[0]==3){assert(c[1]==1250);baud2400=true;}
  if(c[0]==4){assert(c[1]==8);format8n1=true;}}
 assert(baud2400&&format8n1);
 e64_rs232_usb_status_t base{};e64_rs232_usb_status(&base);
 unsigned observations=0,overruns=0,parities=0,frames=0,breaks=0;
 for(unsigned flags:{0u,0x02u,0x04u,0x08u,0x10u,0x1eu}){
  host.Finish({0x10,(uint8_t)(0x60|flags),0,0x55,0xaa,0xff});tick();
  for(auto want:{0,0x55,0xaa,0xff})assert(e64_rs232_usb_get(&b)==1&&b==want);
  assert(e64_rs232_usb_get(&b)==0);
  ++observations;overruns+=!!(flags&2);parities+=!!(flags&4);frames+=!!(flags&8);breaks+=!!(flags&16);
  e64_rs232_usb_status(&status);
  assert(status.rxStatusObservations==base.rxStatusObservations+observations);
  assert(status.rxOverrunObservations==base.rxOverrunObservations+overruns);
  assert(status.rxParityObservations==base.rxParityObservations+parities);
  assert(status.rxFramingObservations==base.rxFramingObservations+frames);
  assert(status.rxBreakObservations==base.rxBreakObservations+breaks);
 }
 host.Finish({0x10,0x1e});tick();e64_rs232_usb_status(&status);
 assert(e64_rs232_usb_get(&b)==0&&status.rxStatusObservations==base.rxStatusObservations+observations+1);
 assert(status.rxOverrunObservations==base.rxOverrunObservations+overruns+1);
 assert(status.rxParityObservations==base.rxParityObservations+parities+1);
 assert(status.rxFramingObservations==base.rxFramingObservations+frames+1);
 assert(status.rxBreakObservations==base.rxBreakObservations+breaks+1);
 base=status;assert(!e64_rs232_usb_set_baud(1200));host.Finish({0x10,0x1e,0x99});tick();
 e64_rs232_usb_status(&status);assert(e64_rs232_usb_get(&b)==0);
 assert(status.rxStatusObservations==base.rxStatusObservations&&status.rxParityObservations==base.rxParityObservations);
 delete driver;host.Finish({0x10,0x1e,0x99});tick();e64_rs232_usb_status(&status);
 assert(status.rxStatusObservations==base.rxStatusObservations&&status.rxBreakObservations==base.rxBreakObservations);
 e64_rs232_usb_close();tick();
 hardware_framing_regression();
 automatic_discovery_regression();
 assert(CUSBEndpoint::alive==1); // Only parent's endpoint 0 remains.
 puts("PASS USB: production FTDI/serial/request/bridge; explicit VID/PID/index selection, defaults, raw IN/OUT, divisors, headers, reconnect, deferred/abandoned cleanup");
}
