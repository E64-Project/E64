#include <circle/fs/partition.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <atomic>
#include <thread>
#include <vector>
static unsigned checks;
#define CHECK(x) do{assert(x);checks++;}while(0)
static TDeviceSyncRequest request(){return {sizeof(TDeviceSyncRequest),DEVICE_SYNC_VERSION,DeviceSyncCompleted,555};}
struct Parent: CDevice {
 enum Mode{Unsupported,Completed,Failed,DispatchFailed,NoResponse,InvalidOutcome,InvalidVersion,Inconsistent,FailureWithoutError,ReportedAndDispatchFailed,PositiveDispatchFailed};
 Mode mode=Unsupported;std::atomic<u64> lastseek{0};std::atomic<unsigned> calls{0},seeks{0},reads{0},writes{0};
 int Read(void*,size_t)override{reads++;return -1;}int Write(const void*,size_t)override{writes++;return -1;}u64 Seek(u64 n)override{seeks++;lastseek=n;return n;}
 int IOCtl(unsigned long cmd,void*data)override{
  calls++;assert(cmd==DEVICE_IOCTL_SYNC_STATUS);assert(DeviceSyncRequestValid(data));auto*p=(TDeviceSyncRequest*)data;
  switch(mode){case Unsupported:return CDevice::IOCtl(cmd,data);case Completed:p->nOutcome=DeviceSyncCompleted;p->nError=0;return 0;case Failed:p->nOutcome=DeviceSyncFailed;p->nError=-823;return 0;case DispatchFailed:return -771;case PositiveDispatchFailed:return 271;case NoResponse:return 0;case InvalidOutcome:p->nOutcome=99;return 0;case InvalidVersion:p->nVersion=99;return 0;case Inconsistent:p->nOutcome=DeviceSyncCompleted;p->nError=-487;return 0;case FailureWithoutError:p->nOutcome=DeviceSyncFailed;p->nError=0;return 0;case ReportedAndDispatchFailed:p->nOutcome=DeviceSyncFailed;p->nError=-911;return -915;}return -1;
 }
};
int main(){
 CDevice device;auto q=request();CHECK(device.IOCtl(DEVICE_IOCTL_SYNC_STATUS,&q)==0);CHECK(q.nOutcome==DeviceSyncUnsupported&&q.nError==0);CHECK(device.IOCtl(DEVICE_IOCTL_SYNC,nullptr)==-1);CHECK(device.IOCtl(0xabcdef,nullptr)==-1);
 Parent parent;CPartition a(&parent,10,100),b(&parent,200,100),nested(&a,0,10);CDevice*targets[]={&device,&a};
 for(CDevice*target:targets){
  CHECK(target->IOCtl(DEVICE_IOCTL_SYNC_STATUS,nullptr)==DEVICE_SYNC_REQUEST_ERROR);
  for(u32 size:{0U,8U,15U,17U,0xffffffffU}){q=request();q.nSize=size;auto saved=q;CHECK(target->IOCtl(DEVICE_IOCTL_SYNC_STATUS,&q)!=0);CHECK(!memcmp(&q,&saved,sizeof q));}
  for(u32 version:{0U,2U,0xffffffffU}){q=request();q.nVersion=version;auto saved=q;CHECK(target->IOCtl(DEVICE_IOCTL_SYNC_STATUS,&q)!=0);CHECK(!memcmp(&q,&saved,sizeof q));}
  alignas(TDeviceSyncRequest) unsigned char raw[sizeof(q)+8];memset(raw,0x5a,sizeof raw);unsigned char saved[sizeof raw];memcpy(saved,raw,sizeof raw);CHECK(target->IOCtl(DEVICE_IOCTL_SYNC_STATUS,raw+1)!=0);CHECK(!memcmp(raw,saved,sizeof raw));
  alignas(TDeviceSyncRequest) u32 header[2]={8,1};CHECK(target->IOCtl(DEVICE_IOCTL_SYNC_STATUS,header)!=0);CHECK(header[0]==8&&header[1]==1);
 }
 CHECK(parent.calls==0);q=request();CHECK(a.IOCtl(DEVICE_IOCTL_SYNC,&q)==-1);CHECK(a.IOCtl(0xabcdef,&q)==-1);CHECK(parent.calls==0);
 for(auto mode:{Parent::Unsupported,Parent::Completed,Parent::Failed,Parent::DispatchFailed,Parent::NoResponse,Parent::InvalidOutcome,Parent::InvalidVersion,Parent::Inconsistent,Parent::FailureWithoutError,Parent::ReportedAndDispatchFailed,Parent::PositiveDispatchFailed}){
  parent.mode=mode;
  for(CDevice*target:{(CDevice*)&a,(CDevice*)&b,(CDevice*)&nested}){
   q=request();int rc=target->IOCtl(DEVICE_IOCTL_SYNC_STATUS,&q);
   if(mode==Parent::Unsupported){CHECK(rc==0&&q.nOutcome==DeviceSyncUnsupported&&q.nError==0);}
   else if(mode==Parent::Completed){CHECK(rc==0&&q.nOutcome==DeviceSyncCompleted&&q.nError==0);}
   else if(mode==Parent::Failed){CHECK(rc==0&&q.nOutcome==DeviceSyncFailed&&q.nError==-823);}
   else if(mode==Parent::DispatchFailed){CHECK(rc==-771&&q.nOutcome==DeviceSyncFailed&&q.nError==-771);}
   else if(mode==Parent::PositiveDispatchFailed){CHECK(rc==271&&q.nOutcome==DeviceSyncFailed&&q.nError==271);}
   else if(mode==Parent::ReportedAndDispatchFailed){CHECK(rc==-915&&q.nOutcome==DeviceSyncFailed&&q.nError==-911);}
   else {CHECK(rc!=0&&q.nOutcome==DeviceSyncFailed&&q.nError!=0);if(mode==Parent::Inconsistent)CHECK(q.nError==-487);}
  }
 }
 CHECK(parent.reads==0&&parent.writes==0&&parent.seeks==0);
 CDevice unsupported;CPartition u(&unsupported,0,100);q=request();CHECK(u.IOCtl(DEVICE_IOCTL_SYNC_STATUS,&q)==0&&q.nOutcome==DeviceSyncUnsupported);
 // Metadata forwarding is stateless; independent parents need no global lock.
 Parent other;CPartition c(&other,0,100);parent.mode=Parent::Failed;other.mode=Parent::Completed;
 std::vector<std::thread> threads;for(int n=0;n<8;n++)threads.emplace_back([&,n]{CDevice*target=n%3==0?(CDevice*)&a:n%3==1?(CDevice*)&b:(CDevice*)&c;for(int i=0;i<1000;i++){auto r=request();assert(target->IOCtl(DEVICE_IOCTL_SYNC_STATUS,&r)==0);assert(r.nOutcome==(target==&c?DeviceSyncCompleted:DeviceSyncFailed));assert(r.nError==(target==&c?0:-823));}});
 for(auto&t:threads){t.join();}CHECK(parent.seeks==0&&parent.reads==0&&parent.writes==0&&other.seeks==0&&other.reads==0&&other.writes==0);
 // Existing partition Seek/Read/Write forwarding still goes through its parent.
 CHECK(a.Seek(0)==0&&parent.lastseek==5120);char data[512];CHECK(a.Read(data,sizeof data)==-1);CHECK(a.Write(data,sizeof data)==-1);CHECK(parent.seeks==1&&parent.reads==1&&parent.writes==1);
 printf("PASS: %u B2 contract checks +8000 concurrent calls: outcomes/errors/versions/sizes/alignment/legacy/nested/shared/independent partitions; zero storage I/O from new contract\n",checks);
}
