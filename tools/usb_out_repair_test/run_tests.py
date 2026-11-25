#!/usr/bin/env python3
"""Execute actual DWHCI accounting + mass-storage Configure/Command, with hardware doubles."""
from pathlib import Path
import re,subprocess,tempfile
root=Path(__file__).resolve().parents[2]
def function(s,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+re.escape(name)+r'\s*\([^;]*?\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]+'\n'
stagefile=root/'third_party/circle-stdlib/libs/circle/lib/usb/dwhcixferstagedata.cpp'
base=root/'tools/fs_stage2a_test/run_tests.py';ns={'__file__':str(base)};ss=base.read_text();exec(ss[:ss.index('with tempfile.TemporaryDirectory')],ns)
# Use real register-bit definitions, with platform MMIO expressions never evaluated.
bits=(root/'third_party/circle-stdlib/libs/circle/include/circle/usb/dwhci.h').read_text();a=bits.index('\t#define DWHCI_HOST_CHAN_INT_XFER_COMPLETE');b=bits.index('#define DWHCI_HOST_CHAN_INT_MASK',a);defines=bits[a:b]
head=ns['pre']+defines+r'''
#define MAX_BULK_TRIES 8
enum {EndpointTypeBulk,EndpointTypeControl,EndpointTypeInterrupt,EndpointTypeIsochronous};
struct StageEndpoint {int type=EndpointTypeBulk;unsigned skipped=0;int GetType(){return type;}void SkipPID(unsigned n,bool){skipped+=n;}};
struct StageURB {bool IsCompleteOnNAK(){return false;}unsigned GetNumIsoPackets(){return 1;}unsigned GetIsoPacketSize(unsigned){return 0;}};
class CDWHCITransferStageData {public:
 bool m_bIn=false,m_bSplitTransaction=false,m_bSplitComplete=false,m_bStatusStage=false;
 unsigned m_nTransactionStatus=0,m_nErrorCount=0,m_nPacketsPerTransaction,m_nBytesPerTransaction,m_nMaxPacketSize=512,m_nTotalBytesTransfered=0,m_nPackets,m_nIsoPackets=0,m_nTransferSize;
 char buffer[65536];void*m_pBufferPointer=buffer;StageEndpoint endpoint;StageEndpoint*m_pEndpoint=&endpoint;StageURB urb;StageURB*m_pURB=&urb;
 CDWHCITransferStageData(unsigned n,bool in):m_bIn(in),m_nPacketsPerTransaction((n+511)/512),m_nBytesPerTransaction(n),m_nPackets((n+511)/512),m_nTransferSize(n){}
 bool IsIsochronous(){return endpoint.type==EndpointTypeIsochronous;}
 void TransactionComplete(u32,u32,u32);u32 GetResultLen()const;
};
'''
def stagecode(text):return function(text,'CDWHCITransferStageData::TransactionComplete')+function(text,'CDWHCITransferStageData::GetResultLen')
tests=r'''
int main(){
 for(unsigned n:{31U,512U,1024U,32768U}){
  CDWHCITransferStageData out(n,false);out.TransactionComplete(0x23,0,n);assert(out.GetResultLen()==n);assert(out.m_nPackets==0);assert(out.m_pBufferPointer==out.buffer+n);
  CDWHCITransferStageData normal(n,false);normal.TransactionComplete(0x23,0,0);assert(normal.GetResultLen()==n);
  CDWHCITransferStageData in(n,true);in.TransactionComplete(0x23,0,0);assert(in.GetResultLen()==n);
 }
 CDWHCITransferStageData shortin(36,true);shortin.TransactionComplete(0x23,0,31);assert(shortin.GetResultLen()==5);
 CDWHCITransferStageData shortout(1024,false);shortout.TransactionComplete(0x23,1,512);assert(shortout.GetResultLen()==512);
 CDWHCITransferStageData noout(31,false);noout.TransactionComplete(0x23,1,31);assert(noout.GetResultLen()==0);
 for(unsigned status:{2U,0x22U,0x12U,0x42U,0xa3U,0xbU,7U,0x103U,0x203U,0x403U}){
  CDWHCITransferStageData fail(31,false);fail.TransactionComplete(status,0,31);assert(fail.GetResultLen()==0);
 }
 CDWHCITransferStageData control(31,false);control.endpoint.type=EndpointTypeControl;control.TransactionComplete(0x23,0,31);assert(control.GetResultLen()==0);
 CDWHCITransferStageData intr(31,false);intr.endpoint.type=EndpointTypeInterrupt;intr.TransactionComplete(0x23,0,31);assert(intr.GetResultLen()==0);
 CDWHCITransferStageData split(31,false);split.m_bSplitTransaction=true;split.TransactionComplete(0x23,0,31);assert(split.GetResultLen()==0);
 puts("PASS: actual DWHCI production completion: captured OUT 0x23/0xc000001f, IN full/short, OUT full/partial/zero, error/NAK/NYET, non-bulk/split isolation");
}
'''
# Reuse only the existing full Configure harness definitions, not diagnostic assertions.
fixture=Path(__file__).with_name('init_harness.py').read_text()
env={'ns':ns,'root':root,'re':re};exec(fixture,env)
u=env['u'];u=u.replace('return script.cbw;','return CapturedOut(script.cbw);')
integration=r'''
int CapturedOut(int result){if(result<0)return result;CDWHCITransferStageData s(31,false);s.TransactionComplete(0x23,result==31?0:1,31);return s.GetResultLen();}
'''
init=r'''
int main(int argc,char**argv){assert(argc==2);bool success=std::string(argv[1])=="normal";script.cbw=success?31:std::string(argv[1])=="short"?30:-1;
 for(int i=0;i<3;i++){auto*d=new CUSBBulkOnlyMassStorageDevice;assert(d->Configure()==success);}
 assert(CDeviceNameService::count==(success?3:0));printf("PASS: real mass Configure/Command/partition-read + real DWHCI accounting, three devices: %s\n",argv[1]);
}
'''
# Before/after reproduction uses the untouched pre-repair driver source backup.
old=root/'build/E64-stage2a-usb-repair/before/third_party/circle-stdlib/libs/circle/lib/usb/dwhcixferstagedata.cpp'
with tempfile.TemporaryDirectory(prefix='e64-usb-out-') as tmp:
 t=Path(tmp)
 def run(name,code,args=[()],expected=0):
  f=t/(name+'.cpp');f.write_text(code);exe=t/name
  subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-variable','-fsanitize=undefined','-pthread',str(f),'-o',str(exe)],check=True)
  for a in args:
   r=subprocess.run([str(exe),*a],capture_output=True,text=True,timeout=30);assert (r.returncode==0)==(expected==0),(name,r.stdout,r.stderr);print(r.stdout,end='')
   if expected:
    assert r.returncode==-6 and 'out.GetResultLen()==n' in r.stderr,(r.returncode,r.stderr)
    print('PASS: original driver reproduces captured OUT accounting failure (assertion rejects zero result)')
 run('before',head+stagecode(old.read_text())+tests,expected=1)
 run('after',head+stagecode(stagefile.read_text())+tests)
 code=head+stagecode(stagefile.read_text())+integration+'\n#include <string>\n#include <cstdarg>\n'+ns['structs']+u+env['partition']+env['bodies']+init
 run('initialization',code,[(x,) for x in ['normal','short','failure']])
print('PASS: USB OUT repair regression tests; no real storage accessed')
