# Exercise the actual controller opt-in cancellation/early completion branches.
import re
source=(circle/'lib/usb/dwhcidevice.cpp').read_text()
def function(name):
 m=re.search(r'^void CDWHCIDevice::'+name+r'\s*\([^;]*?\{',source,re.M);assert m
 return source[m.start():source.index('\n}',m.end())+2]
cancel=function('CancelDeviceTransactions')
channel=function('ChannelInterruptHandler')
channel=channel[:channel.index('\n\tswitch (pStageData->GetSubState ())')]+'\n ++normal;\n}'
code=r'''
#include <cassert>
#include <cstdio>
#include <circle/usb/usbrequest.h>
#include <circle/usb/usbdevice.h>
#define USE_USB_SOF_INTR 1
#define FIQ_LEVEL 2
static unsigned criticalDepth;
static void EnterCritical(unsigned){assert(!criticalDepth);++criticalDepth;}
static void LeaveCritical(){assert(criticalDepth==1);--criticalDepth;}
class CDWHCITransferStageData {public:CUSBDevice*device;CUSBRequest*urb;
CUSBDevice*GetDevice(){return device;}CUSBRequest*GetURB(){return urb;}};
class CDWHCIDevice {public:
 bool m_bShutdown=false,m_bRootPortEnabled=true;unsigned m_nChannels=3;
 CDWHCITransferStageData*m_pStageData[3]{};unsigned aborts=0,normal=0,freed=0;
 struct Queue{void FlushDevice(CUSBDevice*){assert(criticalDepth==1);}}m_TransactionQueue;
 void AbortActiveChannels(){assert(criticalDepth==1);++aborts;}
 void DisableChannelInterrupt(unsigned){}
 void FreeChannel(unsigned){++freed;}
 void CompleteRequest(CUSBRequest*u){u->CallCompletionRoutine();}
 void CancelDeviceTransactions(CUSBDevice*);
 void ChannelInterruptHandler(unsigned);
};
'''+cancel+'\n'+channel+r'''
static void cleanup(void*c){++*static_cast<unsigned*>(c);}
static void done(CUSBRequest*u,void*,void*){assert(!u->GetStatus());assert(u->GetUSBError()==USBErrorAborted);delete u;}
int main(){
 CUSBDevice a,b;CUSBEndpoint endpoint;unsigned cleaned=0;char data[64];
 auto*opted=new CUSBRequest(&endpoint,data,64);opted->SetOwnerCleanup(cleanup,&cleaned);opted->SetCompletionRoutine(done,nullptr,nullptr);
 CUSBRequest legacy(&endpoint,data,64),other(&endpoint,data,64);other.SetOwnerCleanup(cleanup,&cleaned);
 CDWHCIDevice host;
 host.m_pStageData[0]=new CDWHCITransferStageData{&a,opted};
 host.m_pStageData[1]=new CDWHCITransferStageData{&a,&legacy};
 host.m_pStageData[2]=new CDWHCITransferStageData{&b,&other};
 host.CancelDeviceTransactions(&a);assert(!criticalDepth);
 assert(opted->IsCancelled()&&!legacy.IsCancelled()&&!other.IsCancelled());
 host.ChannelInterruptHandler(0);assert(cleaned==1&&host.freed==1&&!host.m_pStageData[0]&&host.normal==0);
 host.ChannelInterruptHandler(1);assert(host.normal==1);host.ChannelInterruptHandler(2);assert(host.normal==2);
 delete host.m_pStageData[1];delete host.m_pStageData[2];
 puts("PASS cancellation: production device-match marking and cancelled IRQ cleanup; legacy and other-device paths unchanged");
}
'''
(t/'cancellation.cpp').write_text(code)
exe=t/'cancellation'
run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=undefined','-include',t/'cstring_first.h','-I'+str(t),'-I'+str(circle/'include'),t/'cancellation.cpp',circle/'lib/usb/usbrequest.cpp','-o',exe]);run([exe])
