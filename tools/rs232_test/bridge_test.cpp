#include "rs232_usb_bridge.h"
#include <cassert>
#include <vector>
#include <deque>
#include <cstdio>

class Port : public Rs232UsbPort {
public:
  bool pending=false, input=false, failConfig=false, failSubmit=false, error=false, delayed=false;
  unsigned baud=0, configurations=0;
  std::vector<uint8_t> output;
  std::deque<uint8_t> receive;
  unsigned written=0;
  bool Configure(unsigned b) override { ++configurations; baud=b; return !failConfig; }
  bool Idle() const override { return !pending; }
  int Submit(bool in,const uint8_t *p,unsigned count) override {
    assert(!pending);
    if (failSubmit) return -1;
    input=in;pending=true;
    if (!in) { output.insert(output.end(),p,p+count);written=count; }
    return 1;
  }
  int Poll(uint8_t *p,unsigned count) override {
    if (delayed) return -2;
    assert(pending);pending=false;
    if (error) return -1;
    if (!input) return written;
    unsigned n=0;
    while(n<count&&!receive.empty()) {p[n++]=receive.front();receive.pop_front();}
    return n;
  }
};
static void drain(Rs232UsbBridge &b,Port &p,unsigned n=1000){for(unsigned i=0;i<n;++i)b.Service(&p,b.Status().adapter);}
// Metadata is supplied by the adapter; the bridge must not decode raw FTDI bits.
class StatusPort : public Port {
public:
  Rs232UsbReceiveStatus observation{};
  int PollWithStatus(uint8_t *p,unsigned count,Rs232UsbReceiveStatus *status) override {
    if(status)*status={};
    bool wasInput=input;
    int result=Poll(p,count);
    if(status&&result>=0&&wasInput)*status=observation;
    return result;
  }
};
static void same_observations(const Rs232UsbStatus &a,const Rs232UsbStatus &b){
 assert(a.rxStatusObservations==b.rxStatusObservations);
 assert(a.rxOverrunObservations==b.rxOverrunObservations);
 assert(a.rxParityObservations==b.rxParityObservations);
 assert(a.rxFramingObservations==b.rxFramingObservations);
 assert(a.rxBreakObservations==b.rxBreakObservations);
}
static void receive_status_regression(){
 Rs232UsbBridge bridge;StatusPort port;uint8_t byte=0;
 assert(!bridge.Open(1,2400));bridge.Service(&port,1);
 assert(bridge.Status().ready&&port.baud==2400&&port.input);
 auto complete=[&](){bridge.Service(&port,1);};
 for(unsigned kind=0;kind<6;++kind){
  port.observation={true,0x10,0x60,kind==1||kind==5,kind==2||kind==5,
                    kind==3||kind==5,kind==4||kind==5};
  auto before=bridge.Status();
  for(auto value:{0,0x55,0xaa,0xff})port.receive.push_back(value);
  complete();auto after=bridge.Status();
  assert(after.rxStatusObservations==before.rxStatusObservations+1);
  assert(after.rxOverrunObservations==before.rxOverrunObservations+(kind==1||kind==5));
  assert(after.rxParityObservations==before.rxParityObservations+(kind==2||kind==5));
  assert(after.rxFramingObservations==before.rxFramingObservations+(kind==3||kind==5));
  assert(after.rxBreakObservations==before.rxBreakObservations+(kind==4||kind==5));
  // Four delivered bytes produce one observation, including combined errors.
  for(auto value:{0,0x55,0xaa,0xff})assert(bridge.Get(&byte)==1&&byte==value);
  assert(!bridge.Get(&byte));
 }
 auto before=bridge.Status();complete();auto after=bridge.Status(); // Status only.
 assert(!bridge.Get(&byte)&&after.rxStatusObservations==before.rxStatusObservations+1);
 assert(after.rxParityObservations==before.rxParityObservations+1);
 assert(after.rxOverrunObservations==before.rxOverrunObservations+1);
 assert(after.rxFramingObservations==before.rxFramingObservations+1);
 assert(after.rxBreakObservations==before.rxBreakObservations+1);
 before=after;port.delayed=true;complete();same_observations(before,bridge.Status());
 port.delayed=false;
 // Header-invalid completion (e.g. NAK) cannot inherit the previous flags.
 port.observation={};complete();same_observations(before,bridge.Status());
 // OUT completion must not count even when the adapter has an IN observation.
 assert(!bridge.Put(0x42));complete();assert(!port.input);
 port.observation={true,0x10,0x1e,true,true,true,true};
 before=bridge.Status();complete();same_observations(before,bridge.Status());
 assert(port.output.size()==1&&port.output[0]==0x42&&port.input);
 // Old baud and close/reopen epochs reject both payload and observations.
 before=bridge.Status();port.receive.push_back(0x99);
 assert(!bridge.SetBaud(1200));complete();same_observations(before,bridge.Status());assert(!bridge.Get(&byte));
 before=bridge.Status();port.receive.push_back(0x88);bridge.Close();assert(!bridge.Open(1,2400));
 complete();same_observations(before,bridge.Status());assert(!bridge.Get(&byte));
 // Failed completion does not reuse the last successful status.
 port.error=true;before=bridge.Status();complete();same_observations(before,bridge.Status());
 assert(!bridge.Status().ready&&bridge.Status().errors==before.errors+1);
 // Disconnect clears the outstanding association; replacement has no status.
 bridge.Removed(&port);same_observations(before,bridge.Status());
 Port replacement;bridge.Service(&replacement,1);drain(bridge,replacement,4);
 same_observations(before,bridge.Status());assert(bridge.Status().ready&&replacement.baud==2400);
}
class FramingPort : public StatusPort {
public:
 unsigned parity=0,bits=8,stops=1;
 bool ConfigureLine(unsigned rate,unsigned p,unsigned d,unsigned s) override {
  assert(!pending);parity=p;bits=d;stops=s;return Configure(rate);
 }
};
static void framing_bridge_regression(){
 for(unsigned rate:{300u,600u,1200u,2400u,9600u})for(unsigned parity=0;parity<3;++parity)
 for(unsigned bits:{7u,8u})for(unsigned stops:{1u,2u}){
  Rs232UsbBridge bridge;FramingPort port;uint8_t byte=0;
  assert(!bridge.OpenConfigured(16,rate,parity,bits,stops));bridge.Service(&port,16);
  auto state=bridge.Status();assert(state.ready&&state.adapter==16&&port.baud==rate);
  assert(port.parity==parity&&port.bits==bits&&port.stops==stops);
  assert(!bridge.SetFraming(parity,bits,stops));assert(bridge.Status().epoch==state.epoch);
  assert(bridge.SetFraming(3,bits,stops)==-1&&bridge.SetFraming(parity,9,stops)==-1);
  assert(bridge.SetFraming(parity,bits,3)==-1&&bridge.Status().epoch==state.epoch);
  assert(bridge.OpenConfigured(1,rate,3,bits,stops)==-1);
  assert(bridge.Status().adapter==16&&bridge.Status().ready);
  // Queue old TX and delay an old RX completion while changing the format.
  assert(!bridge.Put(0xa5));port.receive.push_back(0x99);
  port.observation={true,0x10,0x1e,true,true,true,true};port.delayed=true;
  unsigned nextParity=(parity+1)%3;
  assert(!bridge.SetFraming(nextParity,bits,stops));
  assert(!bridge.Status().ready&&!bridge.Status().txQueued&&bridge.Status().epoch==state.epoch+1);
  assert(!bridge.Get(&byte));bridge.Service(&port,16);assert(port.configurations==1);
  port.delayed=false;bridge.Service(&port,16);
  assert(bridge.Status().ready&&port.configurations==2&&port.parity==nextParity);
  same_observations(state,bridge.Status());assert(!bridge.Get(&byte)&&port.output.empty());
  // New-epoch flagged payload is delivered and counted once, without discard.
  port.receive.push_back(0x55);port.receive.push_back(0x7f);bridge.Service(&port,16);
  assert(bridge.Get(&byte)==1&&byte==0x55&&bridge.Get(&byte)==1&&byte==0x7f);
  assert(bridge.Status().rxParityObservations==state.rxParityObservations+1);
  assert(!bridge.Put(0x42));bridge.Service(&port,16);assert(!port.input);
  // A late old-format OUT is consumed before configuration, never replayed.
  assert(!bridge.SetFraming(parity,bits,stops));bridge.Service(&port,16);
  assert(port.output.size()==1&&port.output[0]==0x42&&port.parity==parity);
  bridge.Removed(&port);FramingPort replacement;bridge.Service(&replacement,16);
  assert(bridge.Status().ready&&replacement.parity==parity&&replacement.bits==bits&&replacement.stops==stops);
  replacement.failConfig=true;assert(!bridge.SetFraming(nextParity,bits,stops));
  bridge.Service(&replacement,16);assert(!bridge.Status().ready);
  unsigned attempts=replacement.configurations;drain(bridge,replacement,4);assert(replacement.configurations==attempts);
  replacement.failConfig=false;assert(!bridge.OpenConfigured(16,rate,nextParity,bits,stops));
  bridge.Service(&replacement,16);assert(bridge.Status().ready);
 }
 // Legacy port implementations support default 8N1, and explicitly reject
 // custom formats rather than silently configuring the wrong line format.
 Rs232UsbBridge legacy;Port port;
 assert(!legacy.Open(1,2400));legacy.Service(&port,1);assert(legacy.Status().ready&&port.baud==2400);
 assert(!legacy.SetFraming(1,7,2));legacy.Service(&port,1);assert(!legacy.Status().ready);
}
// Deterministically interleave an emulator selection change after discovery's
// entry check, at an existing virtual port boundary. No threads or timing race
// is required to exercise the production bridge's subsequent validation.
class SelectionRacePort : public FramingPort {
public:
 Rs232UsbBridge *bridge=nullptr;
 mutable bool changeOnIdle=true;
 bool Idle() const override {
  if(changeOnIdle){changeOnIdle=false;assert(!bridge->Select(2));
   assert(!bridge->OpenConfigured(2,1200,0,8,1));}
  return FramingPort::Idle();
 }
};
static void discovery_bridge_regression(){
 for(unsigned selection=0;selection<=E64_RS232_USB_AUTO;++selection){
  Rs232UsbBridge b;assert(!b.Select(selection));b.PublishDiscovery(0x8005);
  auto d=b.Discovery();unsigned expected=selection==E64_RS232_USB_AUTO?1:
      (selection==1||selection==3||selection==16?selection:0);
  assert(d.requested==selection&&d.resolved==expected&&d.compatibleMask==0x8005&&!d.ready);
  auto epoch=b.Status().epoch;
  assert(b.Select(18)==-1&&b.Select(~0u)==-1&&b.Status().epoch==epoch);
  assert(b.Discovery().requested==selection);
  b.PublishDiscovery(0xffff8000);d=b.Discovery();
  assert(d.compatibleMask==0x8000&&d.resolved==((selection==16||selection==17)?16u:0u));
 }
 Rs232UsbBridge b;FramingPort port;uint8_t byte=0;
 assert(!b.Select(E64_RS232_USB_AUTO));b.PublishDiscovery(0x8000);
 assert(!b.OpenConfigured(E64_RS232_USB_AUTO,2400,1,7,2));
 b.ServiceAtEpoch(&port,E64_RS232_USB_AUTO,b.Status().epoch);
 assert(b.Discovery().ready&&b.Discovery().resolved==16);
 port.observation={true,0x10,0x1e,true,true,true,true};port.receive.push_back(0x55);
 b.Service(&port,E64_RS232_USB_AUTO);assert(b.Status().rxQueued==1);
 assert(!b.Put(0x42));auto stable=b.Status();auto pending=port.pending;
 for(int i=0;i<10;++i)b.PublishDiscovery(0x8000);
 assert(b.Status().epoch==stable.epoch&&b.Status().rxQueued==1&&b.Status().txQueued==1);
 assert(port.configurations==1&&port.pending==pending);same_observations(stable,b.Status());
 // A stale discovery pass cannot configure after an intervening close/open,
 // even if requested selection has the same value (the ABA case).
 b.Close();assert(b.Discovery().requested==17&&b.Discovery().resolved==16&&!b.Discovery().ready);
 assert(!b.OpenConfigured(17,2400,1,7,2));auto fresh=b.Status();
 b.ServiceAtEpoch(&port,17,stable.epoch);assert(port.configurations==1&&b.Status().epoch==fresh.epoch);
 b.ServiceAtEpoch(&port,17,fresh.epoch);assert(b.Discovery().ready);
 assert(!b.Get(&byte));same_observations(stable,b.Status());
 // Re-resolution invalidates queued data and readiness without resetting totals.
 assert(!b.Put(0x99));fresh=b.Status();b.PublishDiscovery(0x8001);
 assert(b.Discovery().resolved==1&&!b.Discovery().ready&&b.Status().epoch!=fresh.epoch);
 assert(!b.Status().txQueued&&!b.Status().rxQueued);same_observations(stable,b.Status());
 b.Removed(&port);FramingPort next;next.failConfig=true;
 b.ServiceAtEpoch(&next,17,b.Status().epoch);auto fault=b.Status();
 assert(!b.Discovery().ready&&b.Discovery().resolved==1);
 for(int i=0;i<10;++i){b.PublishDiscovery(0x8001);b.Service(&next,17);}
 assert(next.configurations==1&&b.Status().epoch==fault.epoch&&b.Status().errors==fault.errors);
 same_observations(stable,b.Status());
 b.Close();assert(b.Discovery().compatibleMask==0x8001&&b.Discovery().resolved==1&&!b.Discovery().ready);
 assert(!b.Select(0));assert(!b.Discovery().requested&&!b.Discovery().resolved);
 // An in-progress discovery pass must not configure its old candidate using
 // a newly requested selection's settings after the entry epoch check.
 Rs232UsbBridge race;SelectionRacePort oldCandidate;oldCandidate.bridge=&race;
 assert(!race.Select(17));race.PublishDiscovery(3);assert(!race.Open(17,2400));
 race.ServiceAtEpoch(&oldCandidate,17,race.Status().epoch);
 assert(race.Discovery().requested==2&&race.Discovery().resolved==2);
 assert(oldCandidate.configurations==0&&!race.Discovery().ready);
}
int main(){
  discovery_bridge_regression();
  framing_bridge_regression();
  receive_status_regression();
  Rs232UsbBridge b;Port p;uint8_t byte=0x42;
  assert(b.Status().adapter==0&&b.Put(1)==-1&&b.Get(&byte)==0&&byte==0x42);
  assert(b.Open(0,300)==-1&&b.Open(18,300)==-1&&b.Open(1,4800)==-1);
  assert(b.Open(1,300)==0);b.Service(nullptr,b.Status().adapter);assert(!b.Status().ready&&b.Put(1)==-1);
  b.Service(&p,b.Status().adapter);assert(b.Status().ready&&p.baud==300&&p.configurations==1);
  for(unsigned i=0;i<b.Capacity;++i)assert(b.Put((uint8_t)i)==0);
  assert(b.Put(0)==-1&&b.Status().txQueued==b.Capacity);
  drain(b,p);assert(p.output.size()==b.Capacity);
  for(unsigned i=0;i<p.output.size();++i)assert(p.output[i]==(uint8_t)i);
  // Wrap both rings and verify exact binary integrity, including NUL and FF.
  for(unsigned round=0;round<3;++round){
    p.output.clear();for(unsigned i=0;i<511;++i){assert(!b.Put((uint8_t)(i+round)));p.receive.push_back((uint8_t)(i+round));}
    drain(b,p);assert(p.output.size()==511);
    for(unsigned i=0;i<511;++i){assert(p.output[i]==(uint8_t)(i+round));assert(b.Get(&byte)==1&&byte==(uint8_t)(i+round));}
    assert(b.Get(&byte)==0);
  }
  unsigned dropped=b.Status().rxDropped;
  for(unsigned i=0;i<b.Capacity+17;++i)p.receive.push_back((uint8_t)i);
  drain(b,p);assert(b.Status().rxQueued==b.Capacity&&b.Status().rxDropped==dropped+17);
  for(unsigned i=0;i<b.Capacity;++i)assert(b.Get(&byte)==1&&byte==(uint8_t)i);
  assert(b.SetBaud(1200)==0&&!b.Status().ready);drain(b,p,4);assert(p.baud==1200&&b.Status().ready);
  assert(b.SetBaud(0)==-1&&b.Status().baud==1200);
  assert(b.Put(99)==0);b.Removed(&p);assert(!b.Status().ready&&!b.Status().txQueued&&b.Get(&byte)==0);
  assert(b.Put(99)==-1);b.Service(nullptr,b.Status().adapter);Port replacement;b.Service(&replacement,b.Status().adapter);
  assert(b.Status().ready&&replacement.baud==1200);assert(b.Put(123)==0);drain(b,replacement,4);
  assert(replacement.output.size()==1&&replacement.output[0]==123);
  // A pending old-session RX completion must never enter a newly opened session.
  replacement.receive.push_back(0x77);b.Close();assert(!b.Status().ready&&b.Get(&byte)==0);
  assert(b.Open(1,300)==0);drain(b,replacement,4);assert(b.Get(&byte)==0);
  replacement.error=true;drain(b,replacement,2);assert(!b.Status().ready&&b.Status().errors);
  unsigned configs=replacement.configurations;drain(b,replacement,10);assert(replacement.configurations==configs);
  replacement.error=false;b.Close();b.Open(1,300);drain(b,replacement,4);assert(b.Status().ready);
  Port failed;failed.failConfig=true;b.Removed(&replacement);b.Service(&failed,b.Status().adapter);assert(!b.Status().ready);
  configs=failed.configurations;drain(b,failed,10);assert(failed.configurations==configs);
  // Submission failure is latched, and an outstanding request never starts a
  // second transfer until completion. A stale discovery snapshot is ignored.
  Rs232UsbBridge submitFailure;Port bad;bad.failSubmit=true;
  assert(!submitFailure.Open(1,300));submitFailure.Service(&bad,1);
  assert(!submitFailure.Status().ready&&submitFailure.Status().errors==1);
  Rs232UsbBridge delayed;Port slow;slow.delayed=true;
  assert(!delayed.Open(1,300));delayed.Service(&slow,1);
  for(int i=0;i<10;++i)delayed.Service(&slow,1);
  assert(slow.pending&&slow.configurations==1);
  assert(!delayed.Open(2,1200));delayed.Service(&slow,1);
  assert(slow.configurations==1);slow.delayed=false;delayed.Service(&slow,2);
  assert(slow.baud==1200);
  // Sustained full duplex at each baud, followed by physical reconnection.
  for(unsigned rate : {300u,600u,1200u,2400u,9600u}) {
    Rs232UsbBridge traffic;Port wire;
    assert(!traffic.Open(1,rate));drain(traffic,wire,4);assert(wire.baud==rate);
    for(unsigned block=0;block<256;++block) {
      for(unsigned i=0;i<64;++i) {assert(!traffic.Put((uint8_t)(block+i)));wire.receive.push_back((uint8_t)(block+i));}
      drain(traffic,wire,20);
      for(unsigned i=0;i<64;++i){assert(traffic.Get(&byte)==1&&byte==(uint8_t)(block+i));assert(wire.output[block*64+i]==(uint8_t)(block+i));}
    }
    assert(!traffic.Status().rxDropped&&!traffic.Status().txDropped);
    traffic.Removed(&wire);traffic.Service(nullptr,1);Port reconnected;drain(traffic,reconnected,4);
    assert(traffic.Status().ready&&reconnected.baud==rate);
  }
  puts("PASS bridge: ordered raw TX/RX, 4096-byte bounds/wrap/overflow, 300/600/1200/2400 sustained duplex, disconnect/reconnect, stale sessions, bounded faults");
}
