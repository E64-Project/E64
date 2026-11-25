#!/usr/bin/env python3
"""Production diskio.cpp and verbatim USB methods, with deterministic devices.
Host doubles replace Circle hardware/locks, not the transfer algorithms.
"""
from pathlib import Path
import subprocess, tempfile, re
root=Path(__file__).resolve().parents[2]
usb=(root/'third_party/circle-stdlib/libs/circle/lib/usb/usbmassdevice.cpp').read_text()
def method(name):
 m=re.search(r'^(?:int|u64) CUSBBulkOnlyMassStorageDevice::'+name+r'\s*\([^;]*?\{',usb,re.M);assert m,name
 return usb[m.start():usb.index('\n}',m.end())+2]+'\n'
pre=r'''
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <climits>
#include <cstdio>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>
#include <condition_variable>
#include <algorithm>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;using uintptr=uintptr_t;using boolean=bool;
#define TRUE true
#define FALSE false
#define CACHE_ALIGN __attribute__((aligned(64)))
#define IS_CACHE_ALIGNED(p,n) ((((uintptr)(p)&63)==0)&&(((n)&63)==0))
#define DMA_BUFFER(type,name,n) alignas(64) type name[((n)+63)/64*64]
#define PACKED __attribute__((packed))
static std::atomic<unsigned> checks{0};
#define CHECK(x) do {assert(x);checks++;} while(0)
'''
disk=r'''
using BYTE=u8;using UINT=unsigned;using QWORD=u64;using WORD=u16;
#define FF_DEFINED 80386
#define _DISKIO_DEFINED
#ifdef LBA64_TEST
using LBA_t=u64;
#else
using LBA_t=u32;
#endif
#define FF_VOLUMES 7
#define FF_MIN_SS 512
#define FF_MAX_SS 512
#define FF_FS_READONLY 0
using DSTATUS=unsigned;
enum DRESULT{RES_OK,RES_ERROR,RES_WRPRT,RES_NOTRDY,RES_PARERR};
#define STA_NOINIT 1
#define GET_SECTOR_COUNT 1
#define CTRL_SYNC 0
#define GET_SECTOR_SIZE 2
#define CTRL_EJECT 7
#define DEVICE_IOCTL_SYNC 0x10001
class CGenericLock {std::mutex m;public:void Acquire(){m.lock();}void Release(){m.unlock();}};
class CDevice {public:
 std::vector<u8> data;u64 pos=0;std::atomic<int> calls{0},reads{0},writes{0};int seek_error=0,transfer_error=0,fail_call=0;bool unknown_size=false;
 std::mutex block_mutex;std::condition_variable cv;bool block=false,entered=false,release=false;
 CDevice():data(256*1024){}
 void RegisterRemovedHandler(void(*)(CDevice*,void*),void*){}
 u64 GetSize(){return unknown_size?UINT64_MAX:data.size();}
 int IOCtl(unsigned,void*){return -1;}bool RemoveDevice(){return false;}
 u64 Seek(u64 p){calls++;if(seek_error)return seek_error==1?UINT64_MAX:p+512;pos=p;std::this_thread::yield();return p;}
 int transfer(void*p,unsigned n,bool write){
  CHECK(IS_CACHE_ALIGNED(p,n));CHECK(n<=32768);int call=++calls;if(write)writes++;else reads++;
  {std::unique_lock<std::mutex> lk(block_mutex);if(block){entered=true;cv.notify_all();cv.wait(lk,[&]{return release;});}}
  if(transfer_error&&(!fail_call||call==fail_call))return transfer_error==1?-1:transfer_error==2?0:(int)n-1;
  assert(pos+n<=data.size());if(write)memcpy(data.data()+pos,p,n);else memcpy(p,data.data()+pos,n);pos+=n;return n;
 }
 int Read(void*p,unsigned n){return transfer(p,n,false);}int Write(const void*p,unsigned n){return transfer(const_cast<void*>(p),n,true);}
};
static CDevice devices[7];
class CDeviceNameService {public:static CDeviceNameService*Get(){static CDeviceNameService x;return &x;}CDevice*GetDevice(const char*n,bool){const char*names[]={"emmc1","emmc2","umsd1","umsd2","umsd3","ufd1","nvme1"};for(int i=0;i<7;i++)if(!strcmp(n,names[i]))return &devices[i];return nullptr;}};
'''
disk_tests=r'''
int main(){
 for(int d=0;d<7;d++)CHECK(disk_initialize(d)==0);
 alignas(64) u8 aligned[131072];std::vector<u8> v(131072+128);u8*p=v.data()+1;
 CHECK(disk_read(7,p,0,1)==RES_PARERR);CHECK(disk_read(0,nullptr,0,1)==RES_PARERR);CHECK(disk_write(0,nullptr,0,1)==RES_PARERR);CHECK(disk_read(0,p,0,0)==RES_PARERR);
 CHECK(disk_read(0,p,(LBA_t)-1,2)==RES_PARERR);CHECK(disk_read(0,p,0,UINT_MAX)==RES_PARERR);
 CHECK(disk_read(0,(u8*)(UINTPTR_MAX-100),0,1)==RES_PARERR);
#ifdef LBA64_TEST
 CHECK(disk_read(0,p,UINT64_MAX/512+1,1)==RES_PARERR);CHECK(disk_read(0,p,UINT64_MAX/512,1)==RES_PARERR);
#endif
 CDevice*saved=s_pVolume[6];s_pVolume[6]=nullptr;CHECK(disk_read(6,p,0,1)==RES_NOTRDY);s_pVolume[6]=saved;
 for(int fail=1;fail<=2;fail++){devices[0].seek_error=fail;int n=devices[0].reads;CHECK(disk_read(0,p,0,1)==RES_ERROR&&devices[0].reads==n);n=devices[0].writes;CHECK(disk_write(0,p,0,1)==RES_ERROR&&devices[0].writes==n);}devices[0].seek_error=0;
 for(int fail=1;fail<=3;fail++){devices[0].transfer_error=fail;memset(p,0x66,512);CHECK(disk_read(0,p,0,1)==RES_ERROR&&p[0]==0x66);int n=devices[0].writes;CHECK(disk_write(0,p,0,1)==RES_ERROR&&devices[0].writes==n+1);}devices[0].transfer_error=0;
 for(int d=0;d<7;d++)for(unsigned off=0;off<64;off++){
  u8*q=v.data()+off;memset(v.data(),0xA7,v.size());memset(q,0x20+d,65536);
  CHECK(disk_write(d,q,0,128)==RES_OK);CHECK(devices[d].data[65535]==0x20+d);
  memset(q,0,65536);CHECK(disk_read(d,q,0,128)==RES_OK);CHECK(q[0]==0x20+d&&q[65535]==0x20+d);
  if(off){CHECK(v[off-1]==0xA7);}
  CHECK(v[off+65536]==0xA7);
 }
 // Aligned fast path, final partial chunk, and read/write data integrity.
 memset(aligned,0xB9,sizeof(aligned));CHECK(disk_write(0,aligned,0,129)==RES_OK);memset(aligned,0,sizeof(aligned));CHECK(disk_read(0,aligned,0,129)==RES_OK&&aligned[66047]==0xB9);
 // A failure in chunk two must not replay chunk one or issue chunk three.
 devices[0].calls=0;devices[0].transfer_error=3;devices[0].fail_call=4;int n=devices[0].writes;CHECK(disk_write(0,p,0,192)==RES_ERROR&&devices[0].writes==n+2);devices[0].transfer_error=devices[0].fail_call=0;
 // Hold one device inside a transaction. Another device must finish before
 // it is released; a second operation on the same slot must not Seek.
 auto &d=devices[0];d.block=true;d.entered=d.release=false;
 std::thread first([&]{CHECK(disk_read(0,aligned,0,1)==RES_OK);});
 {std::unique_lock<std::mutex> lk(d.block_mutex);d.cv.wait(lk,[&]{return d.entered;});}
 int before=d.calls;std::atomic<bool> started{false},finished{false};
 std::thread same([&]{started=true;u8 b[512];CHECK(disk_read(0,b,1,1)==RES_OK);finished=true;});
 while(!started){std::this_thread::yield();}
 u8 other[512];CHECK(disk_read(1,other,0,1)==RES_OK);CHECK(d.calls==before&&!finished);
 {std::lock_guard<std::mutex> lk(d.block_mutex);d.release=true;}d.cv.notify_all();first.join();same.join();d.block=false;
 // Multiple threads on each of all seven slots, with independent buffers
 // and disjoint sectors, expose seek+transfer interleaving mistakes.
 std::vector<std::thread> threads;
 for(int slot=0;slot<7;slot++)for(int owner=0;owner<3;owner++)threads.emplace_back([&,slot,owner]{
  std::vector<u8> out(1025),in(1025);memset(out.data()+1,slot*4+owner+1,1024);
  for(int k=0;k<80;k++){CHECK(disk_write(slot,out.data()+1,owner*4,2)==RES_OK);CHECK(disk_read(slot,in.data()+1,owner*4,2)==RES_OK);CHECK(!memcmp(out.data()+1,in.data()+1,1024));}
 });for(auto&t:threads)t.join();
 // A single bounced request must not touch another slot's storage.
 memset(s_TransferBuffer,0xD3,sizeof(s_TransferBuffer));CHECK(disk_read(3,p,0,64)==RES_OK);
 for(int slot=0;slot<7;slot++)if(slot!=3){CHECK(std::all_of(s_TransferBuffer[slot],s_TransferBuffer[slot]+32768,[](u8 c){return c==0xD3;}));}
 CHECK(disk_write(0,p,0,0)==RES_PARERR);CHECK(disk_read(0,p,512,1)==RES_PARERR);
 CHECK(sizeof(s_TransferBuffer)==7*32768);for(int slot=0;slot<7;slot++)CHECK(((uintptr)s_TransferBuffer[slot]&63)==0);
 printf("PASS: %u whole production diskio checks (%zu-bit LBA), 7-slot buffers=%zu bytes\n",checks.load(),sizeof(LBA_t)*8,sizeof(s_TransferBuffer));
}
'''
# Use the real packed command layouts and exact modified method bodies.
structs=usb[usb.index('#define MAX_TRIES'):usb.index('CNumberPool CUSBBulkOnlyMassStorageDevice::')]
usb_pre=r'''
#define UMSD_TRANSFER_INVALID (-2)
#define UMSD_BLOCK_SIZE 512
#define UMSD_BLOCK_MASK 511
#define UMSD_BLOCK_SHIFT 9
#define UMSD_MAX_OFFSET 0x1FFFFFFFFFFULL
#define LogError 1
#define LogDebug 2
static const char FromUmsd[]="umsd";
#define HEAP_DMA30 0
static u16 le2be16(u16 n){return __builtin_bswap16(n);}static u32 le2be32(u32 n){return __builtin_bswap32(n);}
class CLogger{public:static CLogger*Get(){static CLogger l;return &l;}void Write(const char*,int,const char*,...) {}};
static bool allocation_fail;static unsigned dma_allocs,dma_frees;static void*last_dma;
class CMemorySystem {public:
 static void *HeapAllocate(size_t n,int){if(allocation_fail)return nullptr;void*p=nullptr;if(posix_memalign(&p,64,n))return nullptr;last_dma=p;dma_allocs++;return p;}
 static void HeapFree(void*p){if(p){CHECK(p==last_dma);dma_frees++;last_dma=nullptr;free(p);}}
};
class Endpoint {public:int number;unsigned GetNumber(){return number;}void ResetPID(){}};
static Endpoint input{1},output{2},control{0};
struct Script{int cbw=31,data=-99,csw=13,control_rc=0;unsigned residue=0,status=0,signature=0x53425355,tag_delta=0;int calls=0,cbws=0,datas=0,csws=0;u32 tag=0;unsigned flags=0,blocks=0,opcode=0;};static Script script;
class CUSBHostController{public:
 int Transfer(Endpoint*e,void*p,unsigned n){script.calls++;
  if(e==&output&&n==31){script.cbws++;TCBW*c=(TCBW*)p;script.tag=c->dCWBTag;script.opcode=c->CBWCB[0];script.flags=c->CBWCB[1];script.blocks=(c->CBWCB[7]<<8)|c->CBWCB[8];return script.cbw;}
  if(e==&input&&n==13){script.csws++;if(script.csw!=13)return script.csw;TCSW*c=(TCSW*)p;c->dCSWSignature=script.signature;c->dCSWTag=script.tag+script.tag_delta;c->dCSWDataResidue=script.residue;c->bCSWStatus=script.status;return 13;}
  script.datas++;int r=script.data==-99?(int)n:script.data;if(r>0&&e==&input)memset(p,0x5C,std::min((unsigned)r,n));return r;
 }
 int ControlMessage(Endpoint*,int,int,int,int,void*,int){return script.control_rc;}
};static CUSBHostController host;
class CUSBBulkOnlyMassStorageDevice {public:
 Endpoint*m_pEndpointIn=&input,*m_pEndpointOut=&output;unsigned m_nCWBTag=0,m_nBlockCount=200000;u64 m_ullOffset=0;int resets=0;
 CUSBHostController*GetHost(){return &host;}Endpoint*GetEndpoint0(){return &control;}
 int Reset(){resets++;return 0;}
 int Read(void*,size_t);int Write(const void*,size_t);int TryRead(void*,size_t);int TryWrite(const void*,size_t);int Command(void*,size_t,void*,size_t,boolean);
};
#define REQUEST_TO_ENDPOINT 0
#define REQUEST_OUT 0
#define CLEAR_FEATURE 0
#define ENDPOINT_HALT 0
'''
usb_tests=r'''
static void reset(){script=Script{};allocation_fail=false;}
int main(){CUSBBulkOnlyMassStorageDevice d;alignas(64) u8 data[1024];u8 space[1100];u8*p=space+1;u8 cmd[6]={SCSI_OP_INQUIRY};
 reset();CHECK(d.Command(cmd,6,nullptr,0,false)==0&&script.datas==0&&script.cbws==1&&script.csws==1);
 reset();script.data=-1;int old_resets=d.resets;CHECK(d.Read(data,512)<0&&script.cbws==MAX_TRIES&&d.resets==old_resets+MAX_TRIES);d.resets=0;
 reset();CHECK(d.Read(data,512)==512&&script.blocks==1);reset();CHECK(d.Write(data,512)==512&&script.flags==SCSI_WRITE_FUA&&d.resets==0);
 for(int n:{0,1,30,-1}){reset();script.cbw=n;CHECK(d.Command(cmd,6,p,36,true)<0&&script.datas==0&&script.csws==0);}
 for(int n:{0,1,12,-1}){reset();script.csw=n;script.control_rc=-1;memset(space,0x77,sizeof(space));CHECK(d.Command(cmd,6,p,36,true)<0&&p[0]==0x77);}
 for(int status:{1,2,255}){reset();script.status=status;CHECK(d.Command(cmd,6,p,36,true)<0);}
 reset();script.signature=0;CHECK(d.Command(cmd,6,p,36,true)<0);reset();script.tag_delta=1;CHECK(d.Command(cmd,6,p,36,true)<0);
 for(int n:{-1,0,100,511,513}){reset();script.data=n;int before=d.resets;CHECK(d.Write(data,512)<0&&script.cbws==1&&d.resets==before);}
 for(int n:{0,100,511,513}){reset();script.data=n;script.residue=n<=512?512-n:0;int before=d.resets;CHECK(d.Read(data,512)<0&&script.cbws==1&&d.resets==before);}
 // Legitimate short variable-length replies copy only received bytes.
 for(unsigned actual:{5U,8U,18U,36U}){reset();script.data=actual;script.residue=36-actual;memset(space,0x77,sizeof(space));CHECK(d.Command(cmd,6,p,36,true)==(int)actual);CHECK(p[actual-1]==0x5C&&p[actual]==0x77&&space[0]==0x77);}
 reset();script.data=8;script.residue=0;CHECK(d.Command(cmd,6,p,36,true)<0);
 reset();script.residue=37;CHECK(d.Command(cmd,6,p,36,true)<0);
 reset();allocation_fail=true;CHECK(d.Write(data,512)==512);reset();allocation_fail=true;int before=d.resets;CHECK(d.Read(p,512)<0&&script.calls==0&&d.resets==before);CHECK(d.Write(p,512)<0&&script.calls==0);
 reset();unsigned allocated=dma_allocs,freed=dma_frees;CHECK(d.Write(p,512)==512);CHECK(dma_allocs==allocated+1&&dma_frees==freed+1);
 reset();script.status=1;allocated=dma_allocs;freed=dma_frees;CHECK(d.Command(cmd,6,p,36,true)<0);CHECK(dma_allocs==allocated+1&&dma_frees==freed+1);
 for(size_t n:{size_t(0),size_t(511),size_t(65536)*512}){reset();CHECK(d.TryRead(data,n)<0&&script.calls==0);CHECK(d.Write(data,n)<0&&script.calls==0);}
 reset();CHECK(d.Write(nullptr,512)<0&&script.calls==0);CHECK(d.TryRead((void*)(UINTPTR_MAX-100),512)<0&&script.calls==0);
 d.m_ullOffset=1;CHECK(d.Write(data,512)<0);d.m_ullOffset=UMSD_MAX_OFFSET+1;CHECK(d.TryRead(data,512)<0);d.m_ullOffset=199999ULL*512;CHECK(d.Write(data,1024)<0);d.m_ullOffset=0;
 reset();CHECK(d.Command(nullptr,6,p,36,true)<0&&script.calls==0);CHECK(d.Command(cmd,5,p,36,true)<0&&script.calls==0);CHECK(d.Command(cmd,6,p,(size_t)INT_MAX+1,true)<0&&script.calls==0);
 // Largest legal nonzero READ/WRITE(10) count does not truncate to zero.
 void*big;CHECK(posix_memalign(&big,64,65535U*512)==0);reset();CHECK(d.Write(big,65535U*512)==65535*512&&script.blocks==65535);free(big);
 CHECK(dma_allocs==dma_frees);
 printf("PASS: %u production USB transfer checks; FUA retained, failed writes not replayed\n",checks.load());
}
'''
with tempfile.TemporaryDirectory(prefix='e64-stage2a-') as tmp:
 t=Path(tmp)
 # Stub only Circle interfaces; compile the complete production adapter.
 for name in ['ff.h','diskio.h','circle/device.h','circle/devicenameservice.h','circle/util.h','circle/types.h','circle/genericlock.h','circle/synchronize.h']:
  f=t/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('/* interface supplied by harness */\n')
 disk_source=pre+disk+'\n#include "'+str(root/'third_party/circle-stdlib/libs/circle/addon/fatfs/diskio.cpp')+'"\n'+disk_tests
 for bits in [32,64]:
  src=t/f'disk{bits}.cpp';src.write_text(disk_source);exe=t/f'disk{bits}'
  args=['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-pthread','-fsanitize=undefined','-I'+tmp,str(src),'-o',str(exe)]
  if bits==64:args.insert(1,'-DLBA64_TEST')
  subprocess.run(args,check=True);subprocess.run([str(exe)],check=True,timeout=30)
 src=t/'usb.cpp';src.write_text(pre+structs+usb_pre+'\n'.join(method(n) for n in ['Read','Write','TryRead','TryWrite','Command'])+usb_tests);exe=t/'usb'
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=undefined',str(src),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True,timeout=30)
# Ensure excluded paths and optional benchmark stay as reviewed.
base=root/'tools/fs_stage2a_test/fixtures'
old=(base/'third_party/circle-stdlib/libs/circle/lib/usb/usbmassdevice.cpp').read_text()
for name in ['Reset']:
 old_method=re.search(r'^int CUSBBulkOnlyMassStorageDevice::'+name+r'\s*\([^;]*?\{',old,re.M)
 assert method(name)==old[old_method.start():old.index('\n}',old_method.end())+2]+'\n'
assert 'SCSIWrite.Flags\t\t\t= SCSI_WRITE_FUA;' in usb
assert 'TRUE) < 5)' in usb and 'TRUE) < 8)' in usb
bench=(root/'src/io_stats_bench.cpp').read_text();assert 'dev->' not in bench and 'GetDevice(' not in bench and 'sd_read(fil' in bench
print('PASS: production adapter and USB methods tested; raw benchmark bypass disabled; reset implementation and FUA unchanged.')
