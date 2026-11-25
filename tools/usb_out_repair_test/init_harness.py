# Host-only USB/partition interface doubles; production Configure/Command bodies extracted unchanged.
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
