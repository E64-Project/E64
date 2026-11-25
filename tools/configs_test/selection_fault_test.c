#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "configs_internal.h"
#include "sd_fs.h"
static int fault;
static sd_file *pending;
sd_file *__real_sd_open(const char *,int);
int __real_sd_write(sd_file *,const void *,unsigned);
int __real_sd_sync(sd_file *);
int __real_sd_close(sd_file *);
int __real_sd_rename(const char *,const char *);
int __real_sd_unlink(const char *);
sd_file *__wrap_sd_open(const char *p,int mode) {
 if(fault==7 && mode==SD_READ && !strcmp(p,"/configs/active.txt"))return 0;
 if(mode==SD_WRITE&&!strcmp(p,"/configs/active.new")) {
  if(fault==1)return 0;
  pending=__real_sd_open(p,mode);return pending;
 }
 return __real_sd_open(p,mode);
}
int __wrap_sd_write(sd_file *f,const void *p,unsigned n) {
 if(f==pending&&fault==2){__real_sd_write(f,p,n/2);return SD_ERROR;}
 return __real_sd_write(f,p,n);
}
int __wrap_sd_sync(sd_file *f){int rc=__real_sd_sync(f);return f==pending&&fault==3?SD_ERROR:rc;}
int __wrap_sd_close(sd_file *f){int bad=f==pending&&pending;int rc=__real_sd_close(f);if(bad)pending=0;return bad&&fault==4?SD_ERROR:rc;}
int __wrap_sd_unlink(const char *p){return fault==5&&!strcmp(p,"/configs/active.txt")?SD_ERROR:__real_sd_unlink(p);}
int __wrap_sd_rename(const char *a,const char *b){return fault==6&&!strcmp(a,"/configs/active.new")?SD_ERROR:__real_sd_rename(a,b);}
int main(void){
 char dir[]="/tmp/e64-select-fault-XXXXXX";assert(mkdtemp(dir));assert(!setenv("SD_TEST_ROOT",dir,1));
 configs_boot_init("C64/PAL/HDMI");
 for(int f=1;f<=6;f++){
  fault=0;assert(configs_switch_to(CONFIGS_FACTORY_NTSC)==CONFIGS_OK);
  fault=f;assert(configs_switch_to(CONFIGS_FACTORY_PAL)==CONFIGS_ERROR);
  fault=0;configs_boot_init("C64/PAL/HDMI");
  // Before unlink, the old complete selection survives. After unlink, the
  // complete pending selection is recovered; partial data never boots.
  assert(!strcmp(configs_running()->id,f==6?CONFIGS_FACTORY_PAL:CONFIGS_FACTORY_NTSC));
 }
 fault=0;assert(configs_switch_to(CONFIGS_FACTORY_PAL)==CONFIGS_OK);
 fault=7;configs_recovery_choice(1);configs_boot_init("C64/NTSC/HDMI");fault=0;
 ActiveFile af;assert(active_file_read(&af)==CONFIGS_OK);
 assert(!strcmp(af.config,CONFIGS_FACTORY_NTSC));
 // Storage failure cannot strand a failed PAL recovery selection.
 assert(configs_switch_to(CONFIGS_FACTORY_PAL)==CONFIGS_OK);
 configs_boot_init("C64/NTSC/HDMI");
 fault=1;configs_factory_machine_failed();fault=0;
 assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 assert(strstr(configs_boot_message(),"Cannot persist"));
 assert(active_file_read(&af)==CONFIGS_OK && !strcmp(af.config,CONFIGS_FACTORY_PAL));
 puts("PASS: unreadable selection deliberate recovery; selection open/partial-write/sync/close/unlink/rename fault recovery");return 0;
}
