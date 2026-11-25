// Independent config protection. No deletion, restoration, timers or cleanup.
#include "configs_internal.h"
#include "../sdcard/sd_fs.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define PP_DIR "/system/protect"
#define PP_ANCHOR "/system/protect.id"
#define PP_SIZE 12288
#define PP_MAX 256
static const char cookie[16]="E64-PROTECT-V1";
static unsigned char current[PP_SIZE], staging[PP_SIZE];
static int loaded, state, chosen;
static volatile int busy;
static char volume[8]="SD";
// The production SDK already uses this provider. Optional only for host tests.
extern const char *circle_get_disk_volume(void) __attribute__((weak));
static const char *failure="";
static uint32_t pp_u32(const unsigned char*p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void pp_set32(unsigned char*p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i));}
static uint32_t pp_checksum(const unsigned char*p){uint32_t c=~0U;for(unsigned i=0;i<PP_SIZE;i++){c^=i>=24&&i<28?0:p[i];for(int j=0;j<8;j++)c=(c>>1)^(0xedb88320U&(0U-(c&1)));}return ~c;}
static char *pp_record(unsigned char*p,unsigned i){return (char*)p+32+i*33;}
static int pp_find(const char*id){for(unsigned i=0;i<pp_u32(current+16);i++)if(!strcmp(pp_record(current,i),id))return (int)i;return -1;}
static int pp_fail(const char*s){failure=s;return CONFIGS_ERROR;}
const char *configs_protection_error(void){return failure;}
static int pp_take(void){return __sync_bool_compare_and_swap(&busy,0,1);}
static void pp_give(void){__sync_lock_release(&busy);}
static int pp_valid(const unsigned char*p){
 if(memcmp(p,"E64PRT1",8)||pp_u32(p+8)!=1||!pp_u32(p+12)||pp_u32(p+16)>PP_MAX||pp_u32(p+24)!=pp_checksum(p))return 0;
 for(unsigned i=0;i<pp_u32(p+16);i++){
  const char*s=(const char*)p+32+i*33;
  if(!memchr(s,0,33)||!configs_id_valid(s)||configs_is_factory(s))return 0;
  for(unsigned j=0;j<i;j++)if(!strcmp(s,(const char*)p+32+j*33))return 0;
 }
 return 1;
}
static void pp_slot_name(int slot,char path[32]){snprintf(path,32,PP_DIR "/STATE%d.BIN",slot);}
static int pp_read_slot(int slot,unsigned char*p){
 char path[32];pp_slot_name(slot,path);sd_file*f=sd_open(path,SD_READ);if(!f)return 0;
 unsigned n=0;int ok=sd_size(f)==PP_SIZE&&sd_read(f,p,PP_SIZE,&n)==SD_OK&&n==PP_SIZE;
 int close_rc=sd_close(f);return ok&&close_rc==SD_OK&&pp_valid(p);
}
static int pp_anchor_ok(void){
 char b[16];unsigned n=0;sd_file*f=sd_open(PP_ANCHOR,SD_READ);if(!f)return 0;
 int ok=sd_size(f)==sizeof(b)&&sd_read(f,b,sizeof(b),&n)==SD_OK&&n==sizeof(b);
 int close_rc=sd_close(f);return ok&&close_rc==SD_OK&&!memcmp(b,cookie,sizeof(b));
}
static int pp_write_slot(int slot,unsigned char*p){
 char path[32];pp_slot_name(slot,path);sd_info info;int rc=sd_stat_info(path,&info);
 if(rc!=SD_NOT_FOUND&&(rc!=SD_OK||info.is_dir||info.size!=PP_SIZE))return 0;
 sd_file*f=sd_open(path,rc==SD_NOT_FOUND?SD_WRITE:SD_UPDATE);if(!f)return 0;
 int ok=sd_seek(f,0)==SD_OK&&sd_write(f,p,PP_SIZE)==SD_OK;
 if(sd_sync(f)!=SD_OK)ok=0;
 if(sd_close(f)!=SD_OK)ok=0;
 if(!ok)return 0;
 f=sd_open(path,SD_READ);if(!f)return 0;
 ok=sd_size(f)==PP_SIZE;char check[256];
 for(unsigned offset=0;ok&&offset<PP_SIZE;offset+=sizeof(check)){
  unsigned got=0;ok=sd_read(f,check,sizeof(check),&got)==SD_OK&&got==sizeof(check)&&!memcmp(check,p+offset,sizeof(check));
 }
 int close_rc=sd_close(f);return ok&&close_rc==SD_OK;
}
void configs_protection_init(const char *system_volume){
 static const char*const names[]={"SD","SD2","USB","USB2","USB3","FD","NVME"};
 if(system_volume&&strlen(system_volume)<sizeof(volume)){
  if(system_volume[0]>='0'&&system_volume[0]<='6'&&!system_volume[1])system_volume=names[system_volume[0]-'0'];
  for(unsigned i=0;i<=strlen(system_volume);i++){char c=system_volume[i];volume[i]=c>='a'&&c<='z'?c-32:c;}
 }
 if(!pp_take())return;
 sd_info info;int dir=sd_stat_info(PP_DIR,&info),anchor=sd_stat_info(PP_ANCHOR,NULL);state=-1;
 if(dir==SD_NOT_FOUND&&anchor==SD_NOT_FOUND){state=0;memset(current,0,sizeof(current));}
 else if(dir==SD_OK&&info.is_dir&&anchor==SD_OK&&pp_anchor_ok()&&pp_read_slot(0,current)&&pp_read_slot(1,staging)){
  uint32_t a=pp_u32(current+12),b=pp_u32(staging+12);
  if(a==b&&!memcmp(current,staging,PP_SIZE)){chosen=0;state=1;}
  else if(a>b&&a-b==1&&pp_u32(current+20)==pp_u32(staging+24)){chosen=0;state=1;}
  else if(b>a&&b-a==1&&pp_u32(staging+20)==pp_u32(current+24)){chosen=1;state=1;memcpy(current,staging,PP_SIZE);}
 }
 loaded=1;if(state<0)failure="Protection records need recovery.\nConfigs remain protected.";pp_give();
}
static void pp_ensure(void){if(!loaded)configs_protection_init(NULL);}
int configs_protection_ready(void){pp_ensure();return state>=0;}
int configs_protection_status(const char *id){
 if(!configs_id_valid(id))return -1;
 if(configs_is_factory(id))return 1;
 pp_ensure();if(!pp_take())return -1;
 int result=state<0?-1:(state==1&&pp_find(id)>=0);pp_give();return result;
}
int configs_is_protected(const char *id){return configs_protection_status(id)!=0;}
int configs_protection_read_begin(void){pp_ensure();return pp_take();}
void configs_protection_read_end(void){pp_give();}
unsigned configs_protected_count(void){return state==1?pp_u32(current+16):0;}
const char *configs_protected_id(unsigned index){return state==1&&index<pp_u32(current+16)?pp_record(current,index):NULL;}
static int pp_initialize(void){
 if(state==1)return 1;
 if(state<0)return 0;
 state=-1;
 if(sd_stat_info(PP_DIR,NULL)!=SD_NOT_FOUND||sd_stat_info(PP_ANCHOR,NULL)!=SD_NOT_FOUND)return 0;
 if(sd_mkdir("/system")!=SD_OK)return 0;
 sd_file*f=sd_open(PP_ANCHOR,SD_WRITE);if(!f)return 0;
 int ok=sd_write(f,cookie,sizeof(cookie))==SD_OK;
 if(sd_sync(f)!=SD_OK)ok=0;
 if(sd_close(f)!=SD_OK)ok=0;
 if(!ok||!pp_anchor_ok()||sd_mkdir(PP_DIR)!=SD_OK)return 0;
 memset(staging,0,sizeof(staging));memcpy(staging,"E64PRT1",8);pp_set32(staging+8,1);pp_set32(staging+12,1);pp_set32(staging+24,pp_checksum(staging));
 if(!pp_write_slot(0,staging)||!pp_write_slot(1,staging))return 0;
 memcpy(current,staging,PP_SIZE);chosen=0;state=1;return 1;
}
int configs_set_protected(const char *id,int on,int confirmed_off){
 if(!configs_id_valid(id)||(on!=0&&on!=1))return pp_fail("Invalid protection request.");
 if(configs_is_factory(id))return on?CONFIGS_OK:pp_fail("Factory configs are permanently protected.");
 pp_ensure();if(!pp_take())return pp_fail("Protection update busy. Try again.");
 int result=CONFIGS_ERROR;ConfigFile pf;
 if(state<0){pp_fail("Protection records need recovery.");goto out;}
 if(config_file_read_raw(id,&pf)!=CONFIGS_OK){pp_fail("Cannot read this config.");goto out;}
 int index=state==1?pp_find(id):-1;
 if((index>=0)==on){result=CONFIGS_OK;goto out;}
 if(!on&&!confirmed_off){pp_fail("Confirm turning protection Off.");goto out;}
 if(!pp_initialize()){pp_fail("Protection write failed.\nRecords need recovery.");goto out;}
 if(on&&pp_u32(current+16)==PP_MAX){pp_fail("Protection records are full.");goto out;}
 if(pp_u32(current+12)==UINT32_MAX){pp_fail("Protection generation exhausted.");goto out;}
 memcpy(staging,current,PP_SIZE);unsigned count=pp_u32(current+16);
 if(on){strcpy(pp_record(staging,count),id);pp_set32(staging+16,count+1);}
 else {memmove(pp_record(staging,(unsigned)index),pp_record(staging,(unsigned)index+1),(count-(unsigned)index-1)*33);memset(pp_record(staging,count-1),0,33);pp_set32(staging+16,count-1);}
 pp_set32(staging+12,pp_u32(current+12)+1);pp_set32(staging+20,pp_u32(current+24));pp_set32(staging+24,pp_checksum(staging));
 if(!pp_write_slot(1-chosen,staging)){state=-1;pp_fail("Protection write failed.\nRecords need recovery.");goto out;}
 chosen=1-chosen;memcpy(current,staging,PP_SIZE);result=CONFIGS_OK;
out:pp_give();return result;
}
// Canonical system-volume policy independent of logical-deletion metadata.
// Return 0 for unrelated volumes; paths use FatFs case/trailing-dot semantics.
static int pp_canonical(const char*path,char out[640]){
 if(!path)return -1;
 const char*colon=strchr(path,':');const char*p=colon?colon+1:path;
 if(colon){
  char v[8];unsigned n=(unsigned)(colon-path);if(!n||n>=sizeof(v))return -1;
  for(unsigned i=0;i<n;i++){char c=path[i];v[i]=c>='a'&&c<='z'?c-32:c;}v[n]=0;
  static const char*const names[]={"SD","SD2","USB","USB2","USB3","FD","NVME"};
  const char*name=v;if(n==1&&v[0]>='0'&&v[0]<='6')name=names[v[0]-'0'];
  const char *actual_volume=circle_get_disk_volume?circle_get_disk_volume():volume;
  if(!actual_volume||strlen(actual_volume)>=sizeof(v))return -1;
  char expected[8];unsigned length=(unsigned)strlen(actual_volume);
  for(unsigned i=0;i<=length;i++){char c=actual_volume[i];expected[i]=c>='a'&&c<='z'?c-32:c;}
  const char *expected_name=expected;
  if(length==1&&expected[0]>='0'&&expected[0]<='6')expected_name=names[expected[0]-'0'];
  if(strcmp(name,expected_name))return 0;
 }
 unsigned used=0;
 while(*p){while(*p=='/'||*p=='\\')p++;if(!*p)break;const char*start=p;while(*p&&*p!='/'&&*p!='\\')p++;unsigned n=(unsigned)(p-start);
  if(n==1&&*start=='.')continue;
  if(n==2&&start[0]=='.'&&start[1]=='.'){while(used&&out[used-1]!='/')used--;if(used)used--;continue;}
  while(n&&(start[n-1]==' '||start[n-1]=='.'))n--;
  if(!n||used+n+2>=640)return -1;
  out[used++]='/';for(unsigned i=0;i<n;i++){char c=start[i];out[used++]=c>='A'&&c<='Z'?c+32:c;}
 }
 out[used]=0;return 1;
}
// Preserve retired root files and both firmware Config namespaces.
static int pp_reserved_path(const char*p){
 if(!strcmp(p,"/configs/" CONFIGS_FACTORY_NTSC)||!strncmp(p,"/configs/" CONFIGS_FACTORY_NTSC "/",sizeof("/configs/" CONFIGS_FACTORY_NTSC "/")-1)||
    !strcmp(p,"/configs/" CONFIGS_FACTORY_PAL)||!strncmp(p,"/configs/" CONFIGS_FACTORY_PAL "/",sizeof("/configs/" CONFIGS_FACTORY_PAL "/")-1))return 1;
 if(!strcmp(p,"/e64set.new")||!strcmp(p,"/e64set.old"))return 1;
 if(!strncmp(p,"/set",4) && strchr(p,'~') && strstr(p,".txt") && !strchr(p+1,'/'))return 1;
 if(!strcmp(p,"/configs/main")||!strncmp(p,"/configs/main/",14))return 1;
 static const char*const files[]={"/vice.ini","/settings.txt","/settings-c64.txt","/settings-c128.txt","/settings-vic20.txt","/settings-plus4.txt","/settings-plus4emu.txt","/settings-pet.txt"};
 for(unsigned i=0;i<sizeof(files)/sizeof(files[0]);i++)if(!strcmp(p,files[i]))return 1;
 return 0;
}
int configs_protection_can_write(const char*path){char p[640];int kind=pp_canonical(path,p);return kind==0||(kind==1&&!pp_reserved_path(p));}
int configs_protection_can_remove(const char*path){char p[640];int kind=pp_canonical(path,p);return kind==0||(kind==1&&p[0]&&strcmp(p,"/configs")&&!pp_reserved_path(p));}
int configs_protection_external_allowed(const char*path,int writing){
 char p[640];int kind=pp_canonical(path,p);if(kind==0)return 1;if(kind<0)return 0;
 if(!strcmp(p,"/system/protect.id")||!strcmp(p,"/system/protect")||!strncmp(p,"/system/protect/",16))return 0;
 return !writing||!pp_reserved_path(p);
}
