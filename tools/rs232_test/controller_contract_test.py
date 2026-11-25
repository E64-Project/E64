#!/usr/bin/env python3
"""Run the real DWHCI stage constructor with the serial caller's timeout.
Only platform/MMIO boundaries are doubled. Keep assertions enabled.
"""
from pathlib import Path
import subprocess, tempfile, os, re
root=Path(__file__).resolve().parents[2]
circle=root/'third_party/circle-stdlib/libs/circle'
def run(cmd,**kw): subprocess.run([str(x) for x in cmd],check=True,timeout=60,**kw)
def function(source,name):
 start=source.index(name);start=source.rfind('\n',0,start)+1
 end=source.index('\n}',start)+2
 return source[start:end]
source=(circle/'lib/usb/dwhcixferstagedata.cpp').read_text()
ctor=function(source,'CDWHCITransferStageData::CDWHCITransferStageData')
# Constructor has a multiline signature; the initial line is retained above.
bodies='\n'.join(function(source,n) for n in ['CDWHCITransferStageData::CDWHCITransferStageData','CDWHCITransferStageData::~CDWHCITransferStageData','boolean CDWHCITransferStageData::IsPeriodic','boolean CDWHCITransferStageData::IsIsochronous'])
caller=(circle/'lib/usb/usbserialhost.cpp').read_text()
m=re.search(r'SubmitAsyncRequest \(urb(?:, (\d+))?\)',caller);assert m
current=int(m[1] or 0)
with tempfile.TemporaryDirectory(prefix='e64-controller-contract-') as tmp:
 t=Path(tmp)
 fixture=Path(__file__).with_name('usb_fixture.py').read_text()
 exec(fixture[:fixture.index("exe=t/'usb'")])
 # Add just the platform accessors used by the real constructor.
 p=t/'circle/usb/usbdevice.h';s=p.read_text().replace('public:TUSBDeviceDescriptor','public:inline static bool split=false;TUSBSpeed GetSpeed(){return split?USBSpeedFull:USBSpeedHigh;}bool IsSplit(){return split;}unsigned GetHubAddress(){return 1;}TUSBDeviceDescriptor');p.write_text(s)
 p=t/'circle/usb/usbendpoint.h';s=p.read_text().replace('#include <circle/usb/usb.h>','#include <circle/usb/usb.h>\n#include <circle/usb/usbdevice.h>').replace('public:inline static int alive=0;','public:inline static int alive=0;inline static TEndpointType type=EndpointTypeBulk;CUSBDevice*GetDevice()const{static CUSBDevice d;return &d;}TUSBPID GetNextPID(bool)const{return USBPIDData0;}').replace('return EndpointTypeBulk;','return type;');p.write_text(s)
 header('circle/sysconfig.h','')
 header('circle/timer.h','#define MSEC2HZ(x) (x)\nclass CTimer{public:static CTimer*Get(){static CTimer t;return &t;}unsigned GetTicks(){return 0;}};')
 header('circle/usb/dwhciframescheduler.h','''class CDWHCIFrameScheduler{public:virtual ~CDWHCIFrameScheduler(){}};
class CDWHCIFrameSchedulerIsochronous:public CDWHCIFrameScheduler{public:explicit CDWHCIFrameSchedulerIsochronous(bool){}};
class CDWHCIFrameSchedulerPeriodic:public CDWHCIFrameScheduler{};
class CDWHCIFrameSchedulerNonPeriodic:public CDWHCIFrameScheduler{};
class CDWHCIFrameSchedulerNoSplit:public CDWHCIFrameScheduler{public:explicit CDWHCIFrameSchedulerNoSplit(bool){}};''')
 code='''#include <circle/usb/usbdevice.h>
#include <circle/usb/dwhcixferstagedata.h>
#include <circle/timer.h>
#include <cassert>
#include <cstdlib>
#define USB_TIMEOUT_NONE 0
#define MAX_ISO_SPLIT_PAYLOAD 188
'''+bodies+'''
int main(int argc,char**argv){assert(argc==4);CUSBDevice::split=atoi(argv[1]);CUSBEndpoint::type=atoi(argv[2])?EndpointTypeInterrupt:EndpointTypeBulk;
 CUSBEndpoint ep;alignas(64) unsigned char data[64]{};CUSBRequest request(&ep,data,64);
 CDWHCITransferStageData stage(0,&request,true,false,atoi(argv[3]));}
'''
 f=t/'contract.cpp';f.write_text(code);exe=t/'contract'
 run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-include',t/'cstring_first.h','-include',t/'circle/util.h','-I'+str(t),'-I'+str(circle/'include'),f,circle/'lib/usb/usbrequest.cpp','-o',exe])
 for split in (0,1):
  old=subprocess.run([str(exe),str(split),'0','50'],capture_output=True,text=True,timeout=10)
  assert old.returncode==-6 and 'EndpointTypeInterrupt' in old.stderr,old.stderr
  print('PASS negative control: original bulk timeout 50 aborts in real DWHCI constructor; split='+str(split))
  run([exe,split,0,current]);run([exe,split,1,50])
 print('PASS: current serial caller accepted for direct/hub bulk; existing interrupt timeout accepted')
