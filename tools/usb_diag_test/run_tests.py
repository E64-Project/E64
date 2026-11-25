#!/usr/bin/env python3
"""RAM recorder, production initialization/transfer observers and read-only HTTP.
No hardware or SD/USB device access; doubles supply controller responses.
"""
from pathlib import Path
import subprocess,tempfile,re,json
root=Path(__file__).resolve().parents[2]
def function(s,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+re.escape(name)+r'\s*\([^;]*?\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]+'\n'
def compile_run(t,name,code,args=()):
 p=t/(name+'.cpp');p.write_text(code);exe=t/name
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-variable','-fsanitize=undefined','-pthread','-I'+str(t),str(p),'-o',str(exe)],check=True)
 for a in args or [()]:subprocess.run([str(exe),*a],check=True,timeout=30)
common=r'''
#define E64_USB_INIT_DIAGNOSTICS 1
#define ARM_ALLOW_MULTI_CORE 1
#include <cassert>
#include <atomic>
#include <thread>
#include <vector>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <algorithm>
#include <circle/usbinitdiag.h>
'''
recorder='\n#include "'+str(root/'src/usb_init_diag.cpp')+'"\n'
core=common+recorder+r'''
int main(int argc,char**argv){const std::string mode=argc>1?argv[1]:"basic";
 if(mode=="basic"){
  UsbInitDiagStatus s;usb_init_diag_status(&s);assert(!s.reserved);
  usb_init_diag_mass_begin(4);assert(usb_init_diag_interested(4));
  for(int n:{0,12,31})usb_init_diag_record(UDI_CBW,4,31,n,1,0x12);
  assert(usb_init_diag_result(UDI_SCSI_RESULT,4,0x12,36,0,-2)==-2);
  usb_init_diag_mass_end(4);assert(!usb_init_diag_interested(4));
  usb_init_diag_status(&s);assert(s.published==4);
  UsbInitDiagEvent e;for(unsigned i=0;i<4;i++){assert(usb_init_diag_read(i,&e)&&e.sequence==i+1);}
  assert(!usb_init_diag_read(2048,&e));
  UsbInitDiagStatus again;usb_init_diag_status(&again);assert(!memcmp(&s,&again,sizeof(s)));
 }else if(mode=="overflow"){
  for(unsigned i=0;i<USB_INIT_DIAG_CAPACITY+17;i++)usb_init_diag_record(UDI_DATA,3,i,i,0,0);
  UsbInitDiagStatus s;usb_init_diag_status(&s);assert(s.reserved==2048&&s.published==2048&&s.full_dropped==17&&s.overflowed);
  UsbInitDiagEvent e;assert(usb_init_diag_read(0,&e)&&e.a==0);assert(usb_init_diag_read(2047,&e)&&e.a==2047);
 }else{
  std::atomic<int> complete{0};std::vector<std::thread> writers;
  for(unsigned unit=0;unit<8;unit++)writers.emplace_back([&,unit]{for(unsigned n=0;n<400;n++)usb_init_diag_record(UDI_DATA,unit,n,n^0x55,~n,0x1234);complete++;});
  while(complete!=8){UsbInitDiagStatus s;usb_init_diag_status(&s);assert(s.published<=s.reserved&&s.reserved<=2048);for(unsigned i=0;i<s.published;i++){UsbInitDiagEvent e;assert(usb_init_diag_read(i,&e)&&e.sequence==i+1&&e.b==(e.a^0x55)&&e.c==~e.a&&e.d==0x1234);}}
  for(auto&t:writers){t.join();}
  UsbInitDiagStatus s;usb_init_diag_status(&s);assert(s.published==s.reserved);assert(s.reserved+s.full_dropped+s.contention_dropped==3200);assert(s.overflowed);
  unsigned last[8]={},seen[8]={};for(unsigned i=0;i<s.published;i++){UsbInitDiagEvent e;assert(usb_init_diag_read(i,&e));assert(!seen[e.unit]||e.a>last[e.unit]);seen[e.unit]++;last[e.unit]=e.a;}
 }
 puts("PASS: production RAM recorder ordering/snapshot/overflow/concurrency");}
'''
# Run the full production Configure and its real partition-manager read.
# Construction/USB endpoints/transport are doubles; initial capacity is ZERO.
base_test=root/'tools/fs_stage2a_test/run_tests.py';ns={'__file__':str(base_test)};source=base_test.read_text();exec(source[:source.index('with tempfile.TemporaryDirectory')],ns)
controller=common+recorder+r"""
struct Dev{unsigned GetAddress(){return 3;}};
struct EP{Dev dev;Dev*GetDevice(){return &dev;}unsigned GetNumber(){return 2;}unsigned IsDirectionIn(){return 0;}unsigned GetType(){return 2;}};
typedef EP CUSBEndpoint;
struct CUSBRequest {unsigned length=0,status=0,error=7;CUSBRequest(EP*,void*,unsigned){}unsigned GetStatus(){return status;}unsigned GetResultLength(){assert(status);return length;}unsigned GetUSBError(){assert(!status);return error;}};
struct CUSBHostController{int submitted=1;unsigned result=0;bool SubmitBlockingRequest(CUSBRequest*r,unsigned){r->status=submitted;r->length=result;return submitted;}int Transfer(EP*,void*,unsigned,unsigned);};
"""+function((root/'third_party/circle-stdlib/libs/circle/lib/usb/usbhostcontroller.cpp').read_text(),'CUSBHostController::Transfer')+r"""
int main(){EP ep;CUSBHostController host;char b[31];usb_init_diag_mass_begin(3);
 unsigned index=0;for(unsigned n:{0U,12U,31U}){host.result=n;assert(host.Transfer(&ep,b,31,0)==(int)n);UsbInitDiagEvent e;assert(usb_init_diag_read(index++,&e)&&e.kind==UDI_CONTROLLER_REQUEST&&e.a==31);assert(usb_init_diag_read(index++,&e)&&e.kind==UDI_CONTROLLER_RESULT&&e.a==1&&e.b==1&&e.c==n);}
 host.submitted=0;assert(host.Transfer(&ep,b,31,0)==-1);UsbInitDiagEvent e;assert(usb_init_diag_read(index+1,&e)&&e.a==0&&e.b==0&&e.c==UINT32_MAX&&e.d==7);
 usb_init_diag_mass_end(3);UsbInitDiagStatus before,after;usb_init_diag_status(&before);host.submitted=1;host.Transfer(&ep,b,31,0);usb_init_diag_status(&after);assert(before.reserved==after.reserved);
 puts("PASS: actual controller Transfer observer records successful zero/short/full URB lengths and submission errors without changing returns");}
"""
websource=(root/'src/webui/webui_usb_diag.cpp').read_text()
web=common+recorder+r"""
struct CSocket{int status=0;std::string text;};
namespace webhttp{class CChunkedResponse{CSocket*s;public:CChunkedResponse(CSocket*p,int status,const char*,const char*mime):s(p){s->status=status;assert(!strcmp(mime,"text/plain; charset=utf-8"));}void Write(const char*p){s->text+=p;}void Printf(const char*f,...){char b[1024];va_list a;va_start(a,f);vsnprintf(b,sizeof(b),f,a);va_end(a);s->text+=b;}bool Failed(){return false;}void Finish(){}};}
"""+function(websource,'usb_diag_name')+function(websource,'WebUiUsbInitDiagnostics')
route=(root/'src/webui/webui.cpp').read_text();start=route.index('  if (strcmp(target,"/api/debug/usb-init")==0)');end=route.index('\n#endif',start);routeblock=route[start:end]
assert (root/'src/webui/webui.cpp').read_text().index('int auth = CheckAuth(request);')<start
web+=r"""
#define FALSE false
static void SendText(CSocket*s,int status,const char*,const char*t){s->status=status;s->text=t;}
static bool request(CSocket*socket,const char*target,bool is_get){
"""+routeblock+r"""
 return false;
}
int main(){usb_init_diag_record(UDI_CBW,3,31,0,1,0x12);usb_init_diag_record(UDI_CSW_STATUS,3,1,8,1,0x53425355);
 UsbInitDiagStatus before,after;usb_init_diag_status(&before);CSocket a,b,c;request(&a,"/api/debug/usb-init",true);request(&b,"/api/debug/usb-init",true);request(&c,"/api/debug/usb-init",false);usb_init_diag_status(&after);
 assert(a.status==200&&a.text==b.text&&c.status==405);assert(a.text.find(USB_INIT_DIAG_ID)!=std::string::npos&&a.text.find("CBW 3 0x0000001f 0")!=std::string::npos&&a.text.find("CSW_STATUS")!=std::string::npos);assert(!memcmp(&before,&after,sizeof(before)));
 puts("PASS: actual plain-text endpoint/route is read-only, non-clearing, GET-only and after authentication");}
"""
pre=ns['pre'];structs=ns['structs'];u=ns['usb_pre']
u=u.replace('#define LogDebug 2','#define LogDebug 2\n#define LogWarning 3\n#define DESCRIPTOR_ENDPOINT 5')
u=u.replace('class Endpoint {public:int number;','struct TUSBEndpointDescriptor {uint8_t bmAttributes,bEndpointAddress;};\nclass Endpoint {public: Endpoint(int n):number(n){} Endpoint(void*,const TUSBEndpointDescriptor*d):number(d->bEndpointAddress&15){} int number;')
a=u.index('struct Script{');b=u.index('class CUSBBulkOnlyMassStorageDevice',a)
u=u[:a]+r'''
struct Script {int cbw=31,opcode=0,cbws=0,csw_length=13,tur_fail=0;unsigned tag=0,residue=0,status=0,inquiry=36,capacity=8;bool csw=false,request_sense=false;};static Script script;
class CUSBHostController{public:
 int Transfer(Endpoint*e,void*p,unsigned n){
  if(e->number==2&&n==31){TCBW*c=(TCBW*)p;script.tag=c->dCWBTag;script.opcode=c->CBWCB[0];script.cbws++;script.csw=c->dCBWDataTransferLength==0;script.residue=0;return script.cbw;}
  if(e->number==1&&script.csw){assert(n==13);if(script.csw_length!=13)return script.csw_length;TCSW*c=(TCSW*)p;c->dCSWSignature=CSWSIGNATURE;c->dCSWTag=script.tag;c->dCSWDataResidue=script.residue;c->bCSWStatus=script.status;if(script.opcode==SCSI_OP_TEST_UNIT_READY&&script.tur_fail){c->bCSWStatus=1;script.tur_fail--;}return 13;}
  assert(e->number==1);unsigned actual=n;
  if(script.opcode==SCSI_OP_INQUIRY)actual=script.inquiry;
  if(script.opcode==SCSI_REQUEST_SENSE){actual=8;script.request_sense=true;}
  if(script.opcode==SCSI_OP_READ_CAPACITY10)actual=script.capacity;
  memset(p,0,actual);
  if(script.opcode==SCSI_OP_READ_CAPACITY10&&actual==8){TSCSIReadCapacityResponse*c=(TSCSIReadCapacityResponse*)p;c->ReturnedLogicalBlockAddress=le2be32(9999);c->BlockLengthInBytes=le2be32(512);}
  script.residue=n-actual;script.csw=true;return actual;
 }
 int ControlMessage(Endpoint*,int,int,int,int,void*,int){return -1;}
};static CUSBHostController host;
class CString {char text[80]={};public:void Format(const char*f,...){va_list a;va_start(a,f);vsnprintf(text,sizeof(text),f,a);va_end(a);}operator const char*()const{return text;}};
class CNumberPool{unsigned next;public:static const unsigned Invalid=0xFFFFFFFF;CNumberPool(unsigned n):next(n){}unsigned AllocateNumber(bool){return next++;}void FreeNumber(unsigned){}};
class CDeviceNameService{public:static int count;static CDeviceNameService*Get(){static CDeviceNameService s;return &s;}template<class T>void AddDevice(const char*n,T*,bool){count++;assert(!strncmp(n,"umsd",4));}};int CDeviceNameService::count=0;
class CTimerShim{public:static CTimerShim*Get(){static CTimerShim t;return &t;}void MsDelay(unsigned){}};
#define CTimer CTimerShim
struct FakeUsbDevice{unsigned address;unsigned GetAddress(){return address;}};
class CUSBFunction {int descriptor=0;static unsigned next;FakeUsbDevice device{++next};public:
 bool Configure(){return true;}unsigned GetNumEndpoints(){return 2;}FakeUsbDevice*GetDevice(){return &device;}
 const void*GetDescriptor(unsigned){static TUSBEndpointDescriptor ds[]={{2,0x81},{2,2}};return descriptor<2?&ds[descriptor++]:nullptr;}
 void ConfigurationError(const char*){assert(false);}
};unsigned CUSBFunction::next=0;
class CPartitionManager;
'''+u[b:]
u=u.replace('class CUSBBulkOnlyMassStorageDevice {public:','class CUSBBulkOnlyMassStorageDevice:public CUSBFunction {public:\n boolean Configure();static CNumberPool s_DeviceNumberPool;unsigned m_nDeviceNumber=0;CPartitionManager*m_pPartitionManager=nullptr;')
u=u.replace('m_pEndpointIn=&input,*m_pEndpointOut=&output','m_pEndpointIn=nullptr,*m_pEndpointOut=nullptr').replace('m_nBlockCount=200000','m_nBlockCount=0')
u=u.replace('int Read(void*,size_t);','u64 Seek(u64 p){m_ullOffset=p;return p;}\n int Read(void*,size_t);')
u+=r'''
CNumberPool CUSBBulkOnlyMassStorageDevice::s_DeviceNumberPool(1);
#define CUSBEndpoint Endpoint
#define FS_BLOCK_SIZE 512
#define MAX_PARTITIONS 4
static const char FromPartitionManager[]="partm";
struct TPartitionEntry {u8 data[4],Type,more[3];u32 LBAFirstSector,NumberOfSectors;} PACKED;
struct TMasterBootRecord {u8 BootCode[446];TPartitionEntry Partition[4];u16 BootSignature;} PACKED;
#define BOOT_SIGNATURE 0xAA55
class CPartition{public:CPartition(CUSBBulkOnlyMassStorageDevice*,unsigned,unsigned){}};
class CPartitionManager {public:CUSBBulkOnlyMassStorageDevice*m_pDevice;CString m_DeviceName;CPartition*m_pPartition[4]={};CPartitionManager(CUSBBulkOnlyMassStorageDevice*d,const CString&n):m_pDevice(d),m_DeviceName(n){}boolean Initialize();};
'''
usb=(root/'third_party/circle-stdlib/libs/circle/lib/usb/usbmassdevice.cpp').read_text();bodies=''
for name in ['Configure','Read','Write','TryRead','TryWrite','Command']:
 m=re.search(r'^(?:int|boolean) CUSBBulkOnlyMassStorageDevice::'+name+r'\s*\([^;]*?\{',usb,re.M);assert m,name;bodies+=usb[m.start():usb.index('\n}',m.end())+2]+'\n'
part=(root/'third_party/circle-stdlib/libs/circle/lib/fs/partitionmanager.cpp').read_text();m=re.search(r'boolean CPartitionManager::Initialize \(void\)\n\{',part);partition=part[m.start():part.index('\n}',m.end())+2]
init_test=r'''
int main(int argc,char**argv){assert(argc==2);std::string mode=argv[1];bool expected=true;
 if(mode=="cbw-zero"){script.cbw=0;expected=false;}if(mode=="cbw-short"){script.cbw=30;expected=false;}if(mode=="cbw-fail"){script.cbw=-1;expected=false;}
 if(mode=="csw-short"){script.csw_length=12;expected=false;}if(mode=="csw-fail"){script.status=1;expected=false;}
 if(mode=="inquiry-short"){script.inquiry=5;}
 if(mode=="inquiry-truncated"){script.inquiry=4;expected=false;}
 if(mode=="capacity-truncated"){script.capacity=4;expected=false;}if(mode=="not-ready")script.tur_fail=1;
 if(mode=="allocation-fail"){allocation_fail=true;expected=false;}
 for(int i=0;i<3;i++){auto*d=new CUSBBulkOnlyMassStorageDevice;assert(d->Configure()==expected);}
 assert(CDeviceNameService::count==(expected?3:0));
 UsbInitDiagStatus s;usb_init_diag_status(&s);assert(!s.overflowed&&!s.contention_dropped&&s.published);
 unsigned begins=0,ends=0,cbws=0,registrations=0,scsi=0,csw=0;bool units[4]={};
 for(unsigned i=0;i<s.published;i++){UsbInitDiagEvent e;assert(usb_init_diag_read(i,&e));if(e.kind==UDI_MASS_BEGIN){begins++;assert(e.unit>=1&&e.unit<=3);units[e.unit]=true;}if(e.kind==UDI_MASS_END){ends++;assert(e.b==(unsigned)expected);}if(e.kind==UDI_CBW){cbws++;assert(e.a==31&&(int)e.b==script.cbw);}if(e.kind==UDI_REGISTERED)registrations++;if(e.kind==UDI_SCSI_RESULT)scsi++;if(e.kind==UDI_CSW_STATUS){csw++;if(mode=="inquiry-short"&&e.b)assert(e.b==31);}}
 assert(begins==3&&ends==3&&units[1]&&units[2]&&units[3]);assert(registrations==(expected?3U:0U));assert(scsi>=3);if(mode=="cbw-zero"||mode=="cbw-short"||mode=="cbw-fail")assert(cbws==3&&csw==0);if(mode=="allocation-fail")assert(cbws==0);if(mode=="not-ready")assert(script.request_sense);
 printf("PASS: production Configure/partition-read diagnostic scenario %s (%u events)\n",argv[1],s.published);
}
'''
with tempfile.TemporaryDirectory(prefix='e64-usb-diag-') as tmp:
 t=Path(tmp);(t/'circle').mkdir()
 (t/'circle/usbinitdiag.h').write_text((root/'third_party/circle-stdlib/libs/circle/include/circle/usbinitdiag.h').read_text())
 (t/'circle/timer.h').write_text('#pragma once\n#include <atomic>\nclass CTimer{public:static unsigned GetClockTicks(){static std::atomic<unsigned> n{0};return n++;}};\n')
 (t/'circle/multicore.h').write_text('#pragma once\nclass CMultiCoreSupport{public:static unsigned ThisCore(){return 0;}};\n')
 for name in ['ff.h','diskio.h','circle/device.h','circle/devicenameservice.h','circle/util.h','circle/types.h','circle/genericlock.h','circle/synchronize.h']:
  (t/name).write_text('/* host interfaces supplied by production adapter harness */\n')
 disk_source=common+recorder+pre+ns['disk']+'\n#include "'+str(root/'third_party/circle-stdlib/libs/circle/addon/fatfs/diskio.cpp')+'"\n'+ns['disk_tests']
 compile_run(t,'disk',disk_source)
 compile_run(t,'controller',controller)
 compile_run(t,'web',web)
 compile_run(t,'recorder',core,[('basic',),('overflow',),('concurrent',)])
 compile_run(t,'init',common+recorder+pre+structs+u+partition+bodies+init_test,[(m,) for m in ['normal','cbw-zero','cbw-short','cbw-fail','csw-short','csw-fail','inquiry-short','inquiry-truncated','capacity-truncated','not-ready','allocation-fail']])
print('PASS: RAM-only USB diagnostic tests')
