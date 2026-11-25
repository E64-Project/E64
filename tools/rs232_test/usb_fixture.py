# Executed by run_tests.py with a temporary include root t and run().
def header(name,text):
 p=t/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#pragma once\n'+text+'\n')
header('assert.h','#include "/usr/include/assert.h"')
header('circle/types.h','''#include <cstdint>
#include <cstddef>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;
using s8=int8_t;using s16=int16_t;using s32=int32_t;using s64=int64_t;
using uintptr=uintptr_t;using boolean=bool;
#define TRUE true
#define FALSE false
''')
header('circle/macros.h','#define PACKED __attribute__((packed))')
header('circle/classallocator.h','#define DECLARE_CLASS_ALLOCATOR\n#define IMPLEMENT_CLASS_ALLOCATOR(x)')
header('circle/synchronize.h','inline void DataMemBarrier(){}\ninline void DataSyncBarrier(){}')
header('circle/util.h','#include <cstring>\n#define DMA_BUFFER(type,name,count) type name[count]')
header('circle/logger.h','''#define LOGMODULE(x) static const char From[]=x;
#define LOGERR(...) ((void)0)
#define LOGWARN(...) ((void)0)
enum {LogError,LogNotice,LogDebug};
class CLogger{public:static CLogger*Get(){static CLogger l;return &l;}template<class...T>void Write(T...){}};
''')
header('circle/string.h','''#include <string>
#include <cstdarg>
#include <cstdio>
class CString {std::string v;public:CString(const char*p=""):v(p){}operator const char*()const{return v.c_str();}
void Format(const char*f,...){char b[80];va_list a;va_start(a,f);vsnprintf(b,sizeof b,f,a);va_end(a);v=b;}
void Append(const char*p){v+=p;}};
''')
header('circle/device.h','''#include <circle/types.h>
#include <map>
#include <string>
class CDevice{public:
 enum TProperty{PropertyVendor,PropertyProduct,PropertySerialNumber,PropertyFunction};
 using TRegistrationHandle=void*;using Removed=void(*)(CDevice*,void*);
 Removed removed=nullptr;void*context=nullptr;
 explicit CDevice(CDevice * =nullptr){}virtual~CDevice(){if(removed)removed(this,context);}
 virtual int Write(const void*,size_t){return -1;}virtual int Read(void*,size_t){return -1;}
 TRegistrationHandle RegisterRemovedHandler(Removed r,void*c=nullptr){removed=r;context=c;return this;}
 void UnregisterRemovedHandler(TRegistrationHandle){removed=nullptr;}
};
''')
header('circle/numberpool.h','''#include <set>
class CNumberPool{std::set<unsigned>used;public:explicit CNumberPool(unsigned){}
unsigned AllocateNumber(bool,const char*){unsigned n=1;while(used.count(n))++n;used.insert(n);return n;}
void FreeNumber(unsigned n){used.erase(n);}};
''')
header('circle/devicenameservice.h','''#include <circle/device.h>
class CDeviceNameService{public:std::map<std::string,CDevice*>devices;
static CDeviceNameService*Get(){static CDeviceNameService s;return &s;}
void AddDevice(const char*p,unsigned n,CDevice*d,bool){devices[std::string(p)+std::to_string(n)]=d;}
void RemoveDevice(const char*p,unsigned n,bool){devices.erase(std::string(p)+std::to_string(n));}
CDevice*GetDevice(const char*p,unsigned n,bool){auto it=devices.find(std::string(p)+std::to_string(n));return it==devices.end()?nullptr:it->second;}
};
''')
header('circle/usb/usbdevice.h','''#include <circle/usb/usb.h>
class CUSBDevice{public:TUSBDeviceDescriptor descriptor{};
CUSBDevice(){descriptor.idVendor=0x0403;descriptor.idProduct=0x6001;descriptor.bcdDevice=0x600;}
const TUSBDeviceDescriptor*GetDeviceDescriptor(){return &descriptor;}};
''')
header('circle/usb/usbendpoint.h','''#include <circle/usb/usb.h>
class CUSBDevice;
enum TEndpointType{EndpointTypeControl,EndpointTypeBulk,EndpointTypeInterrupt,EndpointTypeIsochronous};
class CUSBEndpoint{unsigned size=64;public:inline static int alive=0;
CUSBEndpoint(){++alive;}CUSBEndpoint(CUSBDevice*,const TUSBEndpointDescriptor*d):size(d->wMaxPacketSize){++alive;}
~CUSBEndpoint(){--alive;}unsigned GetMaxPacketSize()const{return size;}TEndpointType GetType()const{return EndpointTypeBulk;}};
''')
header('circle/usb/usbhostcontroller.h','''#include <circle/usb/usbrequest.h>
#include <vector>
#include <array>
#include <cassert>
class CUSBHostController{public:CUSBRequest*pending=nullptr;bool submitOK=true,controlsOK=true;
std::vector<std::array<unsigned,3>>controls;
int Transfer(CUSBEndpoint*,void*,unsigned){assert(false&&"blocking data path");return -1;}
int ControlMessage(CUSBEndpoint*,u8,u8 request,u16 value,u16 index,void*,u16){assert(!pending);controls.push_back({request,value,index});return controlsOK?0:-1;}
bool SubmitAsyncRequest(CUSBRequest*u,unsigned timeout=0){assert(!pending&&timeout==0);if(!submitOK)return false;pending=u;return true;}
void Finish(const std::vector<u8>&bytes={},bool ok=true,int actual=-1){auto*u=pending;assert(u);pending=nullptr;
 if(!bytes.empty()){assert(bytes.size()<=u->GetBufLen());memcpy(u->GetBuffer(),bytes.data(),bytes.size());}
 u->SetStatus(ok);u->SetResultLen(actual>=0?actual:bytes.size());u->CallCompletionRoutine();}
void Abandon(){auto*u=pending;pending=nullptr;delete u;}
};
''')
header('circle/usb/usbfunction.h','''#include <circle/device.h>
#include <circle/string.h>
#include <circle/usb/usbendpoint.h>
#include <circle/usb/usbdevice.h>
class CUSBHostController;class CUSBRequest;
class CUSBFunction:public CDevice{CUSBDevice*device;CUSBHostController*host;unsigned cursor=0;CUSBEndpoint ep0;public:
CUSBFunction(CUSBDevice*d,CUSBHostController*h):device(d),host(h){}
explicit CUSBFunction(CUSBFunction*f):device(f->device),host(f->host){}
virtual bool Configure(){return true;}CUSBDevice*GetDevice(){return device;}
CUSBHostController*GetHost(){return host;}CUSBEndpoint*GetEndpoint0(){return &ep0;}
const TUSBDescriptor*GetDescriptor(unsigned){static TUSBEndpointDescriptor e[2]{};
if(cursor>=2){return nullptr;}auto*p=&e[cursor];p->bmAttributes=2;p->bEndpointAddress=cursor++?2:0x81;p->wMaxPacketSize=64;return reinterpret_cast<TUSBDescriptor*>(p);}
void ConfigurationError(const char*){}
};
''')
header('circle/usb/usbdevicefactory.h','''#include <circle/types.h>
struct TUSBDeviceID{u16 vendor,product;};
#define USB_DEVICE(v,p) v,p
''')
header('circle/timer.h','class CTimer{public:inline static unsigned now=0;static unsigned GetClockTicks(){return now;}};')
# USB driver includes need memcpy prior to the host fake's Finish definition.
header('cstring_first.h','#include <cstring>')
exe=t/'usb'
run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
 '-fsanitize=address,undefined','-fno-omit-frame-pointer','-pthread','-DRASPPI=3',
 '-include',t/'cstring_first.h','-I'+str(t),'-I'+str(circle/'include'),'-I'+str(root/'src'),'-I'+str(root/'third_party/vice-3.3/src'),
 Path(__file__).with_name('usb_test.cpp'),root/'src/rs232_usb.cpp',root/'src/rs232_usb_bridge.cpp',
 circle/'lib/usb/usbserial.cpp',circle/'lib/usb/usbserialhost.cpp',circle/'lib/usb/usbserialft231x.cpp',circle/'lib/usb/usbrequest.cpp','-o',exe])
env=dict(os.environ);env['ASAN_OPTIONS']=env.get('ASAN_OPTIONS','')+':verify_asan_link_order=0:detect_leaks=0'
run([exe],env=env)
exec(Path(__file__).with_name('cancellation_fixture.py').read_text())
exec(Path(__file__).with_name('vice_fixture.py').read_text())
