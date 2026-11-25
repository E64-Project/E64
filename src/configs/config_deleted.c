// Permanent deletion with guarded filesystem removal. Old E64DEL1 records
// are read only at startup and removed only by explicit legacy cleanup.
#include "configs_internal.h"
#include "../sdcard/sd_fs.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define STATE_DIR "/system/deleted"
#define ANCHOR_PATH "/system/deleted.id"
static const char anchor_cookie[16] = "E64-LOGICAL-V1";
#define STATE_SIZE 4096
#define ENTRY_OFFSET 32
#define ENTRY_SIZE 40
#define MAX_DELETED 64
#define MAX_LEASES 32
static unsigned char image[STATE_SIZE];
static unsigned char work[STATE_SIZE];
static int status; // 0 = first use; 1 = validated; -1 = recovery required
static int selected;
static volatile int gate;
static unsigned web_leases;
static char system_volume[8] = "SD";
void configs_set_system_volume(const char *volume) {
   static const char *const names[]={"SD","SD2","USB","USB2","USB3","FD","NVME"};
   if (!volume || strlen(volume) >= sizeof(system_volume)) return;
   if (volume[0]>='0' && volume[0]<='6' && !volume[1]) volume=names[volume[0]-'0'];
   unsigned n=(unsigned)strlen(volume);
   for(unsigned i=0;i<=n;i++){char c=volume[i];system_volume[i]=c>='a'&&c<='z'?c-32:c;}
}
static int (*runtime_guard)(const char *id);
void configs_set_runtime_guard(int (*guard)(const char *id)) { runtime_guard=guard; }
static struct { char id[33]; unsigned count; } leases[MAX_LEASES];
static const char *last_error = "";
static int initialized;
static int references(ActiveFile *af);

static uint32_t get32(const unsigned char *p) {
   return p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static void put32(unsigned char *p, uint32_t v) {
   for (int i=0;i<4;i++) p[i]=(unsigned char)(v>>(i*8));
}
static uint32_t crc(const unsigned char *p) {
   uint32_t v=~0U;
   for (unsigned i=0;i<STATE_SIZE;i++) {
      v ^= i>=24 && i<28 ? 0 : p[i];
      for(int j=0;j<8;j++) v=(v>>1)^(0xedb88320U & (0U-(v&1)));
   }
   return ~v;
}
static unsigned entries(const unsigned char *p) { return get32(p+16); }
static unsigned char *entry(unsigned char *p,unsigned i) { return p+ENTRY_OFFSET+i*ENTRY_SIZE; }
static int find(const char *id) {
   for(unsigned i=0;i<entries(image);i++) if(!strcmp(id,(char*)entry(image,i))) return (int)i;
   return -1;
}
static int lock(void) { return __sync_bool_compare_and_swap(&gate,0,1); }
static void unlock(void) { __sync_lock_release(&gate); }
static int error(const char *s) { last_error=s; return CONFIGS_ERROR; }
const char *configs_management_error(void) { return last_error; }
int configs_management_ready(void) { return status>=0; }

static int valid(const unsigned char *p) {
   if(memcmp(p,"E64DEL1",8) || get32(p+8)!=1 || !get32(p+12) ||
      entries(p)>MAX_DELETED || get32(p+24)!=crc(p)) return 0;
   for(unsigned i=0;i<entries(p);i++) {
      const unsigned char *e=p+ENTRY_OFFSET+i*ENTRY_SIZE;
      if(!memchr(e,0,33) || !configs_id_valid((char*)e) ||
         configs_is_factory((char*)e) || e[33]>3) return 0;
      for(unsigned j=0;j<i;j++) if(!strcmp((char*)e,(char*)(p+ENTRY_OFFSET+j*ENTRY_SIZE))) return 0;
      if(!get32(e+34) || get32(e+34)>get32(p+12))return 0;
      for(unsigned j=38;j<ENTRY_SIZE;j++) if(e[j]) return 0;
   }
   return 1;
}
static int read_slot(int slot,unsigned char *p) {
   char path[32];snprintf(path,sizeof(path),STATE_DIR "/STATE%d.BIN",slot);
   sd_file *f=sd_open(path,SD_READ);if(!f)return 0;
   unsigned got=0;int ok=sd_size(f)==STATE_SIZE && sd_read(f,p,STATE_SIZE,&got)==SD_OK && got==STATE_SIZE;
   int close_rc=sd_close(f);
   return ok && close_rc==SD_OK && valid(p);
}
static int write_slot(int slot,unsigned char *p) {
   char path[32];snprintf(path,sizeof(path),STATE_DIR "/STATE%d.BIN",slot);
   sd_info info;int rc=sd_stat_info(path,&info);
   if(rc!=SD_NOT_FOUND && (rc!=SD_OK || info.is_dir || info.size!=STATE_SIZE))return 0;
   // Existing fixed-size slots keep their allocation; do not truncate them.
   sd_file *f=sd_open(path,rc==SD_NOT_FOUND?SD_WRITE:SD_UPDATE);if(!f)return 0;
   int ok=sd_seek(f,0)==SD_OK && sd_write(f,p,STATE_SIZE)==SD_OK;
   if(sd_sync(f)!=SD_OK)ok=0;
   if(sd_close(f)!=SD_OK)ok=0;
   if(!ok)return 0;
   // Re-read into a bounded temporary buffer, never over the authoritative image.
   unsigned char check[STATE_SIZE];
   return read_slot(slot,check) && !memcmp(check,p,STATE_SIZE);
}
static int anchor_valid(void) {
   char bytes[sizeof(anchor_cookie)];unsigned got=0;
   sd_file *f=sd_open(ANCHOR_PATH,SD_READ);if(!f)return 0;
   int ok=sd_size(f)==sizeof(bytes) && sd_read(f,bytes,sizeof(bytes),&got)==SD_OK && got==sizeof(bytes);
   int close_rc=sd_close(f);
   return ok && close_rc==SD_OK && !memcmp(bytes,anchor_cookie,sizeof(bytes));
}
void configs_logical_init(void) {
   // Called on config initialization, including test/safe-mode initialization.
   // The physical-startup guard and snapshot deliberately survive this call.
   if(!lock())return;
   sd_info info;int rc=sd_stat_info(STATE_DIR,&info);
   int anchor_rc=sd_stat_info(ANCHOR_PATH,NULL);
   status=-1;
   if(rc==SD_NOT_FOUND && anchor_rc==SD_NOT_FOUND){memset(image,0,sizeof(image));status=0;}
   else if(rc==SD_OK && info.is_dir && anchor_rc==SD_OK && anchor_valid() && read_slot(0,image) && read_slot(1,work)) {
      uint32_t a=get32(image+12),b=get32(work+12);
      if(a==b && !memcmp(image,work,STATE_SIZE)){status=1;selected=0;}
      else if(a>b && a-b==1 && get32(image+20)==get32(work+24)){status=1;selected=0;}
      else if(b>a && b-a==1 && get32(work+20)==get32(image+24)){status=1;selected=1;memcpy(image,work,STATE_SIZE);}
   }
   if(status<0)last_error="Deletion records need recovery.\nConfig changes suspended.";
   initialized=1;
   unlock();
}
static int commit(void) {
   uint32_t generation=get32(image+12);
   if(generation==UINT32_MAX)return error("Deletion record limit reached.\nRecovery required.");
   put32(work+12,generation+1);put32(work+20,get32(image+24));put32(work+24,crc(work));
   if(!write_slot(1-selected,work)) {
      status=-1;
      return error("Deletion record write failed.\nConfig files are unchanged.");
   }
   selected=1-selected;memcpy(image,work,STATE_SIZE);return CONFIGS_OK;
}
int configs_is_active(const char *id) {
   if(!configs_id_valid(id))return 0;
   if(configs_is_factory(id))return 1;
   if(!initialized)configs_logical_init();
   if(!lock())return 0;
   int ok=status>=0 && (status==0 || find(id)<0);unlock();return ok;
}
int configs_deleted_count(void) { return status==1?(int)entries(image):0; }
const char *configs_deleted_id(unsigned index) { return status==1 && index<entries(image)?(char*)entry(image,index):NULL; }
int configs_deleted_remaining(const char *id) { if(!configs_id_valid(id))return -1; int i=status==1?find(id):-1;return i<0?-1:entry(image,(unsigned)i)[33]; }

// Strict reads for protection decisions. No default-on-error behavior.
static int text_read(const char *path,char *text,unsigned capacity) {
   sd_file *f=sd_open(path,SD_READ);if(!f)return 0;
   uint32_t n=sd_size(f);unsigned got=0;
   int ok=n<capacity && sd_read(f,text,n+1,&got)==SD_OK && got==n;
   int close_rc=sd_close(f);
   if(!ok || close_rc!=SD_OK || memchr(text,0,got))return 0;
   text[got]=0;return 1;
}
static char *trim(char *s) {
   while(*s==' '||*s=='\t'||*s=='\r')s++;
   char *p=s+strlen(s);while(p>s&&(p[-1]==' '||p[-1]=='\t'||p[-1]=='\r'))*--p=0;
   return s;
}
static int reference_valid(const char *id) {
   if(configs_is_factory(id))return 1;
   char path[256],text[CONFIGS_MAX_FILE_LEN];ConfigFile pf;
   configs_path(id,"config.txt",path,sizeof(path));
   return configs_id_valid(id) && text_read(path,text,sizeof(text)) && config_file_parse(text,&pf)==CONFIGS_OK;
}
static int references(ActiveFile *af) {
   char text[CONFIGS_MAX_FILE_LEN];
   if(sd_stat_info(CONFIGS_DIR "/active.new",NULL)!=SD_NOT_FOUND || !text_read(CONFIGS_ACTIVE_FILE,text,sizeof(text)))return 0;
   active_file_clear(af);unsigned seen=0;char *line=text;
   while(line && *line){
      char *next=strchr(line,'\n');if(next)*next++=0;
      char *key=trim(line);
      if(*key && *key!='#'){
         char *v=strchr(key,'=');if(!v)return 0;*v++=0;key=trim(key);v=trim(v);
         unsigned bit=!strcmp(key,"config")?1:!strcmp(key,"once")?2:0;
         if(!*key || (bit & seen))return 0;
         seen|=bit;
         if(bit==1 || bit==2){if((bit==1 && !*v)||(*v && !configs_id_valid(v)))return 0;strcpy(bit==1?af->config:af->once,v);}
      }
      line=next;
   }
   return (seen&1) && reference_valid(af->config) && (!af->once[0]||reference_valid(af->once));
}
// Inspect saved startup configurations without applying them. A pending
// Start Once can run while the persistent config uses different ROM assets.
static int reference_line(char *line, const char *id) {
   char *value=strchr(line,'=');
   if(!value || *trim(line)=='#')return 0;
   value=trim(value+1);size_t n=strlen(value);
   if(n>=2 && value[0]=='"' && value[n-1]=='"'){value[n-1]=0;value++;}
   return configs_path_belongs(value,id);
}
static int file_references(const char *path, const char *id) {
   sd_info info;int rc=sd_stat_info(path,&info);
   if(rc==SD_NOT_FOUND)return 0;
   if(rc!=SD_OK || info.is_dir || info.size>256*1024)return -1;
   sd_file *file=sd_open(path,SD_READ);if(!file)return -1;
   char line[1024],chunk[256];unsigned used=0,total=0;int result=0;
   for(;;){
      unsigned got=0;if(sd_read(file,chunk,sizeof(chunk),&got)!=SD_OK){result=-1;break;}
      total+=got;if(total>info.size){result=-1;break;}
      if(!got)break;
      for(unsigned i=0;i<got;i++){
         if(!chunk[i] || used>=sizeof(line)-1){result=-1;break;}
         if(chunk[i]=='\n'){line[used]=0;if(reference_line(line,id))result=1;used=0;}
         else line[used++]=chunk[i];
      }
      if(result<0)break;
   }
   if(total!=info.size)result=-1;
   if(result>=0 && used){line[used]=0;if(reference_line(line,id))result=1;}
   if(sd_close(file)!=SD_OK)result=-1;
   return result;
}
static int startup_assets(const char *owner, const char *id) {
   if (configs_is_factory(owner)) return 0;
   static const char *const files[]={"config.txt","vice.ini","settings.txt",
      "settings-c64.txt","settings-c128.txt","settings-vic20.txt",
      "settings-plus4.txt","settings-plus4emu.txt","settings-pet.txt"};
   char path[256];
   for(unsigned i=0;i<sizeof(files)/sizeof(files[0]);i++){
      configs_path(owner,files[i],path,sizeof(path));
      int result=file_references(path,id);if(result)return result;
   }
   return 0;
}

// Check references in every saved Config, not only today's boot selections.
typedef struct { const char *id; int blocked; } ReferenceScan;
static int other_config_references(void *ctx, const char *name, int is_dir) {
   ReferenceScan *scan=ctx;
   if(is_dir && configs_id_valid(name) && !configs_is_factory(name) &&
      strcmp(name,scan->id) && startup_assets(name,scan->id)!=0) scan->blocked=1;
   return scan->blocked;
}
// Keep config.txt until all other contents have been removed so ordinary
// mid-delete errors remain visible/retryable as the same Config.
typedef struct { char folder[256]; int failed; unsigned removed; } Removal;
static int remove_child(void *ctx, const sd_info *info) {
   Removal *r=ctx;
   char lower[SD_MAX_NAME_LEN+1];unsigned i=0;
   do {char c=info->name[i];lower[i]=c>='A'&&c<='Z'?c+32:c;} while(info->name[i++]);
   if(!strcmp(lower,"config.txt"))return 0;
   char path[640];int n=snprintf(path,sizeof(path),"%s/%s",r->folder,info->name);
   unsigned removed=0;
   if(n<=0 || n>=(int)sizeof(path) || sd_remove_tree(path,&removed,NULL,NULL)!=SD_OK)r->failed=1;
   r->removed+=removed;return r->failed;
}
static int remove_config_files(const char *id, int legacy) {
   Removal r;memset(&r,0,sizeof(r));configs_path(id,"",r.folder,sizeof(r.folder));
   size_t n=strlen(r.folder);if(n && r.folder[n-1]=='/')r.folder[n-1]=0;
   sd_info info;int exists=sd_stat_info(r.folder,&info);
   if(exists==SD_NOT_FOUND && legacy)return CONFIGS_OK;
   if(exists!=SD_OK || !info.is_dir)return error("Cannot open Config folder.\nNothing was deleted.");
   if(sd_list_info(r.folder,remove_child,&r)!=SD_OK || r.failed)
      return error("Deletion failed; some files may\nhave been removed. ID reserved.\nRetry or inspect the Config.");
   char metadata[256];configs_path(id,"config.txt",metadata,sizeof(metadata));
   int rc=sd_unlink(metadata);
   if((rc!=SD_OK && rc!=SD_NOT_FOUND) || sd_unlink(r.folder)!=SD_OK ||
      sd_stat_info(r.folder,NULL)!=SD_NOT_FOUND)
      return error("Deletion incomplete.\nConfig folder/ID not released.\nInspect storage before retrying.");
   return CONFIGS_OK;
}
static int permanently_delete(const char *id,int legacy) {
   if(!configs_id_valid(id) || configs_is_factory(id))return error("Factory/invalid Config.\nDeletion is not allowed.");
   if(configs_is_protected(id))return error("Config is protected.\nDeletion is not allowed.");
   if(!strcmp(id,configs_running()->id))return error("Running Config.\nDeletion is not allowed.");
   if(!lock())return error("Config storage is busy.\nTry again when idle.");
   int result=CONFIGS_ERROR;ActiveFile af;
   if(web_leases){error("Web file request is active.\nWait, then try again.");goto out;}
   if(status<0){error("Legacy deletion records\nneed recovery.");goto out;}
   int index=status==1?find(id):-1;
   if((index>=0)!=!!legacy){error("Config state changed.\nRefresh before deleting.");goto out;}
   if(!references(&af)){error("Boot selection unreadable\nor invalid. Deletion refused.");goto out;}
   if(!strcmp(id,af.config)||!strcmp(id,af.once)){error("Power-on or Start Once\nConfig is protected.");goto out;}
   ReferenceScan scan={id,0};
   int rc=sd_list(CONFIGS_DIR,other_config_references,&scan);
   if(rc!=SD_OK || scan.blocked){error("Other Configs reference assets\nor settings are unreadable.");goto out;}
   for(unsigned i=0;i<MAX_LEASES;i++)if(leases[i].count && !strcmp(leases[i].id,id)){error("Config files are in use.\nClose them before deletion.");goto out;}
   if(runtime_guard && runtime_guard(id)){error("Config assets are in use.\nDeletion is not allowed.");goto out;}
   if(!legacy && !reference_valid(id)){error("Cannot read Config metadata.");goto out;}
   if(remove_config_files(id,legacy)!=CONFIGS_OK)goto out;
   if(legacy){
      memcpy(work,image,STATE_SIZE);unsigned n=entries(work);
      memmove(entry(work,(unsigned)index),entry(work,(unsigned)index+1),(n-(unsigned)index-1)*ENTRY_SIZE);
      memset(entry(work,n-1),0,ENTRY_SIZE);put32(work+16,n-1);
      if(commit()!=CONFIGS_OK){error("Files removed, but legacy record\ncleanup failed. ID reserved\nuntil records are recovered.");goto out;}
   }
   configs_list_close();last_error="";result=CONFIGS_OK;
out:unlock();return result;
}
int configs_delete(const char *id) { return permanently_delete(id,0); }
int configs_purge_legacy(const char *id) { return permanently_delete(id,1); }
int configs_restore(const char *id) {
   (void)id;return error("Restore is no longer available.\nReview legacy entries explicitly.");
}
const char *configs_deleted_name(unsigned index) {
   static char name[CONFIGS_MAX_NAME_LEN+1];
   const char *id=configs_deleted_id(index);char path[256],text[CONFIGS_MAX_FILE_LEN];ConfigFile pf;
   if(!id)return "";
   configs_path(id,"config.txt",path,sizeof(path));
   pkv_copy(name,sizeof(name),text_read(path,text,sizeof(text)) && config_file_parse(text,&pf)==CONFIGS_OK?pf.info.name:id);
   return name;
}
// Old retention counters are frozen. Startup never purges or updates them.
void configs_startup_failed(void) { }
void configs_successful_startup(void) { }

// Match canonicalized paths without following aliases. Invalid config IDs
// (including FAT short-name aliases) are refused. Works with explicit volumes.
static int path_id(const char *path,char id[33]) {
   if(!path)return -1;
   const char *colon=strchr(path,':');
   if (colon) {
      static const char *const volumes[]={"SD","SD2","USB","USB2","USB3","FD","NVME"};
      char volume[8];unsigned n=(unsigned)(colon-path);
      if(!n || n>=sizeof(volume))return -1;
      for(unsigned i=0;i<n;i++){char c=path[i];volume[i]=c>='a'&&c<='z'?c-32:c;}volume[n]=0;
      const char *actual=volume;
      if(n==1 && volume[0]>='0'&&volume[0]<='6')actual=volumes[volume[0]-'0'];
      char expected[8];unsigned length=(unsigned)strlen(system_volume);
      for(unsigned i=0;i<=length;i++){char c=system_volume[i];expected[i]=c>='a'&&c<='z'?c-32:c;}
      if(strcmp(actual,expected))return 0;
   }
   const char *p=colon?colon+1:path;
   char canonical[640];unsigned used=0;
   while(*p){while(*p=='/'||*p=='\\')p++;if(!*p)break;const char *s=p;while(*p&&*p!='/'&&*p!='\\')p++;unsigned n=(unsigned)(p-s);
      if(n==1&&*s=='.')continue;
      if(n==2&&s[0]=='.'&&s[1]=='.'){while(used&&canonical[used-1]!='/')used--;if(used)used--;continue;}
      while(n && (s[n-1]==' '||s[n-1]=='.'))n--;
      if(!n)return -1;
      if(used+n+2>=sizeof(canonical))return -1;
      canonical[used++]='/';for(unsigned i=0;i<n;i++){char c=s[i];canonical[used++]=c>='A'&&c<='Z'?c+32:c;}
   }
   canonical[used]=0;
   if(!strcmp(canonical,"/system/deleted.id"))return -1;
   if(!strncmp(canonical,"/system/deleted",15) && (!canonical[15]||canonical[15]=='/'))return -1;
   if(!strcmp(canonical,"/configs"))return 2;
   if(strncmp(canonical,"/configs/",9))return 0;
   const char *s=canonical+9;const char *end=strchr(s,'/');unsigned n=end?(unsigned)(end-s):(unsigned)strlen(s);
   if(!n || n>32)return -1;
   memcpy(id,s,n);id[n]=0;
   return configs_id_valid(id)?1:-1;
}
int configs_path_allowed(const char *path) {
   char id[33];int kind=path_id(path,id);return kind==0 || kind==2 || (kind==1 && configs_is_active(id));
}
int configs_path_acquire(const char *path) {
   char id[33];int kind=path_id(path,id);
   if(kind==0 || kind==2)return 0;
   if(kind<0 || !initialized || !lock())return -1;
   int result=-1;
   if(status>=0 && (status!=1 || find(id)<0)){
      for(unsigned i=0;i<MAX_LEASES;i++)if(leases[i].count && !strcmp(leases[i].id,id)){__sync_fetch_and_add(&leases[i].count,1);result=(int)i+1;goto out;}
      for(unsigned i=0;i<MAX_LEASES;i++)if(!leases[i].count){strcpy(leases[i].id,id);leases[i].count=1;result=(int)i+1;break;}
   }
out:unlock();return result;
}
void configs_path_release(int lease) {
   if(lease<=0 || lease>MAX_LEASES)return;
   // Only short in-memory operations hold gate outside a management commit.
   // A live config lease prevents deleting that config during the commit.
   __sync_fetch_and_sub(&leases[lease-1].count,1);
}
int configs_web_begin(void) {
   if(!lock())return 0;
   __sync_fetch_and_add(&web_leases,1);unlock();return 1;
}
void configs_web_end(void) { __sync_fetch_and_sub(&web_leases,1); }

int configs_path_belongs(const char *path, const char *id) {
   char found[33];return path && configs_id_valid(id) && path_id(path,found)==1 && !strcmp(found,id);
}
int configs_path_is_managed(const char *path) {
   char found[33];return path_id(path,found)!=0;
}
