#!/usr/bin/env python3
"""Fault-inject production Stage 1 functions; no card/device access.
Functions are extracted verbatim, with FatFs/stdio/hardware test doubles.
"""
from pathlib import Path
import re, subprocess, tempfile
root = Path(__file__).resolve().parents[2]
def function(text, name):
    m = re.search(r'^(?:(?:extern "C"|static) )?[\w *]+\b'+re.escape(name)+r'\([^;]*?\{', text, re.M)
    assert m, name
    return text[m.start():text.index('\n}', m.end())+2]+'\n'
def functions(path, names):
    s = (root/path).read_text()
    return '\n'.join(function(s,n) for n in names)
checks=0
def run(tmp, name, source, cpp=False):
    p=Path(tmp)/(name+('.cpp' if cpp else '.c'));p.write_text(source)
    exe=Path(tmp)/name
    subprocess.run(['c++' if cpp else 'cc','-std=c++17' if cpp else '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-variable','-Wno-type-limits','-fsanitize=undefined',str(p),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
pre=r'''
#include <assert.h>
#include <stdint.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef enum {FR_OK,FR_DISK_ERR,FR_INT_ERR,FR_NOT_READY,FR_NO_FILE,FR_NO_PATH,FR_INVALID_NAME,FR_DENIED,FR_EXIST,FR_INVALID_OBJECT,FR_WRITE_PROTECTED,FR_INVALID_DRIVE,FR_NOT_ENABLED,FR_NO_FILESYSTEM,FR_MKFS_ABORTED,FR_TIMEOUT,FR_LOCKED,FR_NOT_ENOUGH_CORE,FR_TOO_MANY_OPEN_FILES,FR_INVALID_PARAMETER} FRESULT;
#define CHECK(x) do { assert(x); count++; } while(0)
static int count;
'''
core=pre+r'''
#include <fcntl.h>
#define MAX_OPEN_FILES 4
#define BMC64_FILETAB_TRACE 0
#define STREAM_MAX_BYTES 0x80000000u
#define SLURP_MAX_BYTES 33554432u
struct FIL {unsigned pos,size;};
struct CircleFile {int in_use,mode,streamed,fopen_called,config_lease;char *contents;unsigned position,size;int allocated,written_to;char fname[32];};
// FIL is a separate member in production; add it to the test handle too.
'''
core=core.replace('char fname[32];','char fname[32];FIL file;')
core+=r'''
static CircleFile fileTab[MAX_OPEN_FILES];
static FRESULT seek_rc,read_rc,unlink_rc,sync_rc,close_rc,write_rc,dir_rc,rewind_rc,dir_close_rc;
static int read_calls,unlink_calls,dir_calls,write_calls;static bool eof,short_write;
static unsigned f_tell(FIL*f){return f->pos;}static unsigned f_size(FIL*f){return f->size;}
static FRESULT f_lseek(FIL*f,unsigned p){if(seek_rc==FR_OK)f->pos=p;return seek_rc;}
static FRESULT f_read(FIL*f,void*p,unsigned n,unsigned*got){read_calls++;*got=read_rc?0:n;if(!read_rc){memset(p,'r',n);f->pos+=n;}return read_rc;}
static FRESULT f_write(FIL*f,void*p,unsigned n,unsigned*got){write_calls++;*got=short_write?n-1:n;return write_rc;}
static FRESULT f_close(FIL*f){return close_rc;}static FRESULT f_sync(FIL*f){return sync_rc;}
static FRESULT f_unlink(char*p){unlink_calls++;return unlink_rc;}
static bool allow=true;
static int configs_path_allowed(const char*p){return allow;}static int configs_protection_can_remove(const char*p){return allow;}static int configs_protection_external_allowed(const char*p,int w){return allow;}
static void configs_path_release(int x){}static void stream_drop_cltbl(CircleFile&f){}
static void stream_setup(CircleFile&f){f.streamed=1;}static int slurp_file(CircleFile&f,int x){return -1;}
static void io_stats_read(int x,unsigned y){}static void io_stats_lseek(){}
struct dirent {char d_name[256];int d_ino,d_type;};
#define DT_DIR 4
#define DT_REG 8
#define AM_DIR 16
struct FATFS_DIR {int n;};
struct FILINFO {char fname[256];int fattrib;uint32_t fsize;};
struct TestDir {int mOpen,mFirstRead,mEntrySizeValid;uint32_t mEntrySize;FATFS_DIR mCurrentEntry;dirent mEntry;};
#define DIR TestDir
struct CircleDir {int in_use,config_lease;};static CircleDir cd;static bool known=true;
static CircleDir* FindCircleDirFromDIR(DIR*d){return known?&cd:nullptr;}
static FRESULT f_readdir(FATFS_DIR*d,FILINFO*f){if(!f)return rewind_rc;dir_calls++;if(!dir_rc){strcpy(f->fname,eof?"":"file");f->fattrib=0;f->fsize=16384;}return dir_rc;}
static FRESULT f_closedir(FATFS_DIR*d){return dir_close_rc;}
static void io_stats_readdir_entry(){}
'''+functions('src/new_io.cpp',['fatfs_errno','read_next_entry','do_readdir','bmc64_directory_entry_size','readdir','readdir_r','closedir','_read','_lseek','_unlink','fsync','_close'])+r'''
int main(){
 CircleFile &f=fileTab[0];f.in_use=1;f.mode=O_RDWR;f.streamed=1;f.fopen_called=1;f.size=100;f.position=5;f.file.pos=0;char buf[8];
 seek_rc=FR_DISK_ERR;CHECK(_read(0,buf,2)==-1&&errno==EIO&&read_calls==0&&f.position==5);
 CHECK(_lseek(0,12,SEEK_SET)==-1&&errno==EIO&&f.position==5);
 seek_rc=FR_OK;CHECK(_lseek(0,12,SEEK_SET)==12&&f.position==12);CHECK(_read(0,buf,2)==2&&f.position==14);
 read_rc=FR_DISK_ERR;CHECK(_read(0,buf,2)==-1&&errno==EIO&&f.position==14);read_rc=FR_OK;
 f.position=f.size;CHECK(_read(0,buf,2)==0);
 char path[]="SD:/file";
 for(int rc=FR_DISK_ERR;rc<=FR_INVALID_PARAMETER;rc++){unlink_rc=(FRESULT)rc;CHECK(_unlink(path)==-1&&errno==fatfs_errno(unlink_rc));}
 unlink_rc=FR_OK;CHECK(_unlink(path)==0);allow=false;int calls=unlink_calls;CHECK(_unlink(path)==-1&&errno==EACCES&&unlink_calls==calls);allow=true;
 DIR d={};d.mOpen=1;d.mFirstRead=1;dirent de,*out;
 rewind_rc=FR_DISK_ERR;CHECK(readdir_r(&d,&de,&out)==EIO&&!out&&d.mFirstRead);
 rewind_rc=FR_OK;dir_rc=FR_NOT_READY;CHECK(readdir_r(&d,&de,&out)==ENODEV&&!out);
 dir_rc=FR_OK;eof=true;errno=EIO;CHECK(readdir_r(&d,&de,&out)==0&&!out&&errno==0);
 eof=false;CHECK(readdir_r(&d,&de,&out)==0&&out==&de&&!strcmp(out->d_name,"file"));
 uint32_t entry_size=0;int before_dir=dir_calls;CHECK(bmc64_directory_entry_size(&d,&entry_size)==0&&entry_size==16384&&dir_calls==before_dir);
 dir_rc=FR_DISK_ERR;CHECK(!readdir(&d)&&errno==EIO);known=false;CHECK(readdir_r(&d,&de,&out)==EBADF&&!out);known=true;
 dir_close_rc=FR_DISK_ERR;CHECK(closedir(&d)==-1&&errno==EIO);
 sync_rc=FR_DISK_ERR;CHECK(fsync(0)==-1&&errno==EIO);sync_rc=FR_OK;CHECK(fsync(0)==0);
 close_rc=FR_DISK_ERR;CHECK(_close(0)==-1&&errno==EIO&&!f.in_use);
 f.in_use=1;f.fopen_called=1;f.mode=O_WRONLY;f.size=3;f.contents=(char*)malloc(3);write_rc=FR_DISK_ERR;close_rc=FR_OK;CHECK(_close(0)==-1&&errno==EIO);
 f.in_use=1;f.fopen_called=1;f.mode=O_WRONLY;f.size=3;f.contents=(char*)malloc(3);write_rc=FR_OK;short_write=true;CHECK(_close(0)==-1);
 f.in_use=1;f.fopen_called=1;f.mode=O_WRONLY;f.size=3;f.contents=(char*)malloc(3);short_write=false;CHECK(_close(0)==0);
 printf("PASS: %d production libc adapter fault/success checks\n",count);
}
'''
sdk=pre+'\n#include "'+str(root/'src/sdcard/sd_fs.h')+'"\n'+r'''
struct sd_file {int n;};static sd_file dummy;
static int open_bad,read_rc,close_rc,write_rc,short_read;static unsigned file_size=3;static int close_calls;
sd_file* sd_open(const char*p,int mode){return open_bad?NULL:&dummy;}
uint32_t sd_size(sd_file*f){return file_size;}
int sd_read(sd_file*f,void*p,unsigned n,unsigned*got){*got=short_read?2:file_size;memset(p,'x',*got);return read_rc;}
int sd_close(sd_file*f){close_calls++;return close_rc;}
int sd_write(sd_file*f,const void*p,unsigned n){return write_rc;}
'''.replace('static sd_file dummy','static struct sd_file dummy')+functions('src/sdcard/sd_fs_file.c',['sd_read_file','sd_write_file'])+r'''
int main(void){char b[16];CHECK(sd_read_file("x",b,16)==3&&!strcmp(b,"xxx"));
 read_rc=SD_DENIED;close_rc=SD_ERROR;CHECK(sd_read_file("x",b,16)==SD_DENIED&&!b[0]);read_rc=SD_OK;
 CHECK(sd_read_file("x",b,16)==SD_ERROR&&!b[0]);close_rc=SD_OK;short_read=1;CHECK(sd_read_file("x",b,16)==SD_ERROR);short_read=0;
 file_size=16;int before=close_calls;CHECK(sd_read_file("x",b,16)==SD_ERROR&&close_calls==before+1);file_size=3;
 open_bad=1;CHECK(sd_read_file("x",b,16)<0);open_bad=0;CHECK(sd_read_file("x",b,0)==SD_INVALID);
 write_rc=SD_DENIED;close_rc=SD_ERROR;CHECK(sd_write_file("x","abc",3)==SD_DENIED);write_rc=SD_OK;CHECK(sd_write_file("x","abc",3)==SD_ERROR);close_rc=SD_OK;CHECK(sd_write_file("x","abc",3)==SD_OK);
 printf("PASS: %d production SDK whole-file fault/success checks\n",count);return 0;}
'''
# Retired root settings must have no startup reader.
assert 'main_file_read' not in (root/'src/configs/config_boot.c').read_text()

# Actual FatFs traversal functions with deterministic directory/device doubles.
fstext=(root/'src/sdcard/sd_fs_fatfs.c').read_text()
state=re.search(r'typedef struct \{\n  FILINFO fi;.*?\} remove_state;',fstext,re.S).group()
traversal=pre+'\n#include "'+str(root/'src/sdcard/sd_fs.h')+'"\n'+r'''
#define FAT_PATH_LEN 640
#define REMOVE_TREE_DEPTH 24
#define AM_DIR 16
typedef struct {int n;} DIR;
typedef struct {char fname[256];unsigned fattrib;} FILINFO;
static FRESULT open_rc,dir_rc,close_rc,unlink_rc;static int entries,unlink_calls,close_calls,child_calls,read_after;
static int fat_path(const char*p,char*out,unsigned n){snprintf(out,n,"%s",p);return 0;}
static int configs_protection_can_remove(const char*p){return 1;}
static FRESULT f_opendir(DIR*d,const char*p){d->n=0;return open_rc;}
static FRESULT f_readdir(DIR*d,FILINFO*f){if(dir_rc&&d->n>=read_after)return dir_rc;strcpy(f->fname,d->n++<entries?"child":"");f->fattrib=0;return FR_OK;}
static FRESULT f_closedir(DIR*d){close_calls++;return close_rc;}
static FRESULT f_unlink(const char*p){unlink_calls++;if(strstr(p,"child"))child_calls++;return unlink_rc;}
static FRESULT f_stat(const char*p,FILINFO*f){f->fattrib=AM_DIR;return FR_OK;}
static void to_info(const FILINFO*f,sd_info*i){memset(i,0,sizeof(*i));strcpy(i->name,f->fname);}
static int visit(void*c,const sd_info*i){return 0;}
'''+function(fstext,'result')+'\n'+state+'\n'+functions('src/sdcard/sd_fs_fatfs.c',['sd_list_info','remove_folder','sd_remove_tree'])+r'''
int main(void){unsigned n;CHECK(sd_list_info("x",visit,0)==SD_OK);dir_rc=FR_DISK_ERR;close_rc=FR_DENIED;CHECK(sd_list_info("x",visit,0)==SD_ERROR);CHECK(sd_remove_tree("x",&n,0,0)==SD_ERROR&&unlink_calls==0&&n==0);
 dir_rc=FR_OK;CHECK(sd_remove_tree("x",&n,0,0)==SD_DENIED&&unlink_calls==0);close_rc=FR_OK;entries=1;unlink_rc=FR_WRITE_PROTECTED;close_rc=FR_DISK_ERR;CHECK(sd_remove_tree("x",&n,0,0)==SD_DENIED&&unlink_calls==1&&child_calls==1&&n==0);
 unlink_calls=child_calls=0;entries=0;close_rc=FR_OK;unlink_rc=FR_OK;CHECK(sd_remove_tree("x",&n,0,0)==SD_OK&&n==1&&unlink_calls==1);
 unlink_calls=0;open_rc=FR_NOT_READY;CHECK(sd_remove_tree("x",&n,0,0)==SD_ERROR&&unlink_calls==0);CHECK(sd_list_info("x",visit,0)==SD_ERROR);
 open_rc=FR_OK;unlink_calls=0;entries=1;dir_rc=FR_DISK_ERR;read_after=1;CHECK(sd_remove_tree("x",&n,0,0)==SD_ERROR&&n==1&&unlink_calls==1);
 dir_rc=FR_OK;unlink_calls=0;close_rc=FR_DENIED;CHECK(sd_remove_tree("x",&n,0,0)==SD_DENIED&&n==1&&unlink_calls==1);
 close_rc=FR_OK;unlink_calls=0;CHECK(sd_remove_tree("x",&n,0,0)==SD_OK&&n==2&&unlink_calls==2);
 printf("PASS: %d production FatFs traversal fault/success checks\n",count);return 0;}
'''
# Finish helpers use real control flow with injected stdio errors. f_close's
# synchronization failure is represented by a failing fclose, as on firmware.
stdio=pre+r'''
static int write_bad,flush_bad,close_bad,flushed,closed;
static int fake_error(FILE*f){if(write_bad)errno=ENOSPC;return write_bad;}
static int fake_flush(FILE*f){flushed++;if(flush_bad)errno=EIO;return flush_bad?-1:0;}
static int fake_close(FILE*f){closed++;if(close_bad)errno=EROFS;return close_bad?-1:0;}
#define ferror fake_error
#define fflush fake_flush
#define fclose fake_close
'''+functions('third_party/common/menu.c',['finish_settings_file'])+functions('third_party/vice-3.3/src/resources.c',['finish_resource_file'])+r'''
int main(void){FILE*f=(FILE*)1;for(int a=0;a<2;a++)for(int b=0;b<2;b++)for(int c=0;c<2;c++){
 write_bad=a;flush_bad=b;close_bad=c;flushed=closed=0;errno=0;int rc=finish_settings_file(f);CHECK((rc!=0)==(a||b||c)&&closed==1&&flushed==!a);if(a||b||c)CHECK(errno==(a?ENOSPC:b?EIO:EROFS));
 flushed=closed=0;errno=0;rc=finish_resource_file(f);CHECK((rc<0)==(a||b||c)&&closed==1&&flushed==!a);if(a||b||c)CHECK(errno==(a?ENOSPC:b?EIO:EROFS));
 }printf("PASS: %d production configuration finish/write/flush/sync-close checks\n",count);return 0;}
'''
resource=pre+r'\n'
resource=pre+r"""
typedef struct {int error,eof,input;} FakeFile;static FakeFile inf,outf;
static int existing=1,open_input_bad,open_output_bad,read_bad,write_bad,flush_bad,close_input_bad,close_output_bad,remove_bad,rename_bad;
static int removed,read_calls,output_calls;
static unsigned num_resources=2;static char *machine_id="C64",*vice_config_file="cfg";
static char *archdep_default_resource_file_name(void){return strdup("cfg");}
static char *lib_stralloc(const char*s){return strdup(s);}static void lib_free(void*p){free(p);errno=ENODEV;}
static int util_file_exists(const char*s){return existing&&!strcmp(s,"cfg");}
static int ioutil_access(const char*s,int m){return 0;}
static char *archdep_make_backup_filename(const char*s){return strdup("cfg.bak");}
static int ioutil_remove(const char*s){removed++;if(remove_bad)errno=EACCES;return remove_bad?-1:0;}
static int ioutil_rename(const char*a,const char*b){if(rename_bad)errno=EIO;return rename_bad?-1:0;}
static FakeFile* fake_open(const char*s,const char*m){if((m[0]=='r'&&open_input_bad)||(m[0]=='w'&&open_output_bad)){errno=ENOSPC;return NULL;}return m[0]=='r'?&inf:&outf;}
static int fake_error(FakeFile*f){return f->error;}static int fake_eof(FakeFile*f){return f->eof;}
static void fake_setbuf(FakeFile*f,void*p){}
static int fake_flush(FakeFile*f){if(flush_bad){errno=EIO;return -1;}return 0;}
static int fake_close(FakeFile*f){if(f->input?close_input_bad:close_output_bad){errno=EROFS;return -1;}return 0;}
static int fake_print(FakeFile*f,const char*fmt,...){output_calls++;if(write_bad){f->error=1;errno=ENOSPC;return -1;}return 1;}
static int util_get_line(char*b,int n,FakeFile*f){read_calls++;if(read_bad){f->error=1;errno=EBADMSG;return -1;}if(read_calls==1){strcpy(b,"[C64]");return 5;}f->eof=1;return -1;}
static int check_emu_id(const char*s){return !strcmp(s,"[C64]");}
static int resource_item_isdefault(unsigned i){return 0;}
static void write_resource_item(FakeFile*f,unsigned i){fake_print(f,"item");}
#define FILE FakeFile
#define fopen fake_open
#define ferror fake_error
#define feof fake_eof
#define setbuf fake_setbuf
#define fflush fake_flush
#define fclose fake_close
#define fprintf fake_print
#define log_message(...) ((void)0)
#define MODE_READ_TEXT "r"
#define MODE_WRITE_TEXT "w"
#define IOUTIL_ACCESS_W_OK 2
"""
resource+='\n'.join(re.findall(r'^#define RESERR_.*$',(root/'third_party/vice-3.3/src/resources.h').read_text(),re.M))+'\n'
resource+=functions('third_party/vice-3.3/src/resources.c',['finish_resource_file','resources_save','resources_dump'])+r"""
static void reset(void){inf=(FakeFile){0,0,1};outf=(FakeFile){0};existing=1;open_input_bad=open_output_bad=read_bad=write_bad=flush_bad=close_input_bad=close_output_bad=remove_bad=rename_bad=removed=read_calls=output_calls=0;}
int main(void){reset();CHECK(resources_save("cfg")==0&&removed==1&&output_calls>0);
 reset();write_bad=1;close_output_bad=1;CHECK(resources_save("cfg")==-1&&errno==ENOSPC&&removed==0);
 reset();read_bad=1;close_input_bad=close_output_bad=1;CHECK(resources_save("cfg")==RESERR_READ_ERROR&&errno==EBADMSG&&removed==0);
 reset();flush_bad=1;close_output_bad=1;CHECK(resources_save("cfg")==-1&&errno==EIO&&removed==0);
 reset();close_output_bad=1;CHECK(resources_save("cfg")==-1&&errno==EROFS&&removed==0);
 reset();close_input_bad=1;CHECK(resources_save("cfg")==RESERR_READ_ERROR&&removed==0);
 reset();open_output_bad=1;close_input_bad=1;CHECK(resources_save("cfg")==RESERR_CANNOT_CREATE_FILE&&errno==ENOSPC&&removed==0);
 reset();remove_bad=1;CHECK(resources_save("cfg")==RESERR_CANNOT_REMOVE_BACKUP&&errno==EACCES);
 reset();rename_bad=1;CHECK(resources_save("cfg")==RESERR_CANNOT_RENAME_FILE&&output_calls==0);
 reset();open_input_bad=1;CHECK(resources_save("cfg")==RESERR_READ_ERROR);
 reset();existing=0;CHECK(resources_save("cfg")==0&&removed==0);
 reset();CHECK(resources_dump("dump")==0);reset();write_bad=1;CHECK(resources_dump("dump")==-1);reset();flush_bad=1;CHECK(resources_dump("dump")==-1);reset();close_output_bad=1;CHECK(resources_dump("dump")==-1);
 printf("PASS: %d production VICE save/dump caller fault/success checks\n",count);return 0;}
"""
ioutil=pre+r"""
#define _DIRENT_HAVE_D_TYPE 1
#define DT_UNKNOWN 0
#define DT_DIR 4
#define DT_LNK 10
#define FSDEV_DIR_SEP_STR "/"
typedef struct {int n,pass;} DIR;static DIR handle;
struct dirent {int d_type;char d_name[64];};static struct dirent entry;
typedef struct {char *name;} ioutil_name_table_t;
typedef struct {ioutil_name_table_t *dirs,*files;int dir_amount,file_amount,counter;} ioutil_dir_t;
static int dirs_amount,files_amount,pass,open_bad,read_bad_pass,close_bad,stat_bad,items=2,fill_items=2,unknown_type;
static DIR *opendir(const char*p){pass++;if(open_bad==pass){errno=ENODEV;return NULL;}handle=(DIR){0,pass};return &handle;}
static struct dirent *readdir(DIR*d){if(read_bad_pass==d->pass){errno=EIO;return NULL;}int n=d->pass==2?fill_items:items;if(d->n>=n)return NULL;snprintf(entry.d_name,64,"f%d",d->n);entry.d_type=unknown_type?DT_UNKNOWN:(d->n%2?8:DT_DIR);d->n++;return &entry;}
static int closedir(DIR*d){if(close_bad){errno=EROFS;return -1;}return 0;}
static int ioutil_check_dir_filter(struct dirent*d,int m){return 1;}
static char *util_concat(const char*a,const char*b,const char*c,void*d){return strdup(c);}
static int ioutil_stat(const char*p,unsigned*l,unsigned*isdir){if(stat_bad){errno=EACCES;return -1;}*isdir=0;return 0;}
#define lib_malloc malloc
#define lib_calloc calloc
#define lib_free free
#define lib_stralloc strdup
static int ioutil_compare_names(const void*a,const void*b){return strcmp(((const ioutil_name_table_t*)a)->name,((const ioutil_name_table_t*)b)->name);}
void ioutil_closedir(ioutil_dir_t*);
"""+functions('third_party/vice-3.3/src/ioutil.c',['ioutil_read_dir','ioutil_count_dir_items','ioutil_filldir','ioutil_opendir','ioutil_closedir'])+r"""
static void reset(void){pass=open_bad=read_bad_pass=close_bad=stat_bad=unknown_type=0;items=fill_items=2;}
int main(void){reset();ioutil_dir_t*d=ioutil_opendir("x",0);CHECK(d&&d->dir_amount==1&&d->file_amount==1);ioutil_closedir(d);
 reset();read_bad_pass=1;close_bad=1;CHECK(!ioutil_opendir("x",0)&&errno==EIO);
 reset();read_bad_pass=2;CHECK(!ioutil_opendir("x",0)&&errno==EIO);
 reset();open_bad=2;CHECK(!ioutil_opendir("x",0)&&errno==ENODEV);
 reset();close_bad=1;CHECK(!ioutil_opendir("x",0)&&errno==EROFS);
 reset();fill_items=3;CHECK(!ioutil_opendir("x",0)&&errno==EIO);
 reset();fill_items=1;CHECK(!ioutil_opendir("x",0)&&errno==EIO);
 reset();unknown_type=stat_bad=1;CHECK(!ioutil_opendir("x",0)&&errno==EACCES);
 reset();unknown_type=1;d=ioutil_opendir("x",0);CHECK(d&&d->file_amount==2);ioutil_closedir(d);
 printf("PASS: %d production VICE directory caller fault/success checks\n",count);return 0;}
"""
menu_source=(root/'third_party/common/menu.c').read_text()
save_body=function(menu_source,'save_settings_to')
menu_save=pre+r"""
#include <stdarg.h>
typedef struct {int error;} FakeFile;static FakeFile output;
static int open_bad,write_bad,flush_bad,close_bad,emux_bad,emux_calls,closed,logged;
static FakeFile* fake_open(const char*p,const char*m){if(open_bad){errno=EACCES;return NULL;}return &output;}
static int fake_error(FakeFile*f){if(f->error)errno=ENOSPC;return f->error;}
static int fake_flush(FakeFile*f){if(flush_bad){errno=EIO;return -1;}return 0;}
static int fake_close(FakeFile*f){closed++;if(close_bad){errno=EROFS;return -1;}return 0;}
static int fake_print(FakeFile*f,const char*fmt,...){if(write_bad){f->error=1;errno=ENOSPC;return -1;}return 1;}
static int emux_save_settings(const char*p){emux_calls++;if(emux_bad)errno=EIO;return emux_bad?-1:0;}
static void emux_save_additional_settings(FakeFile*f){}
static void emux_log_settings_file(const char*p){logged++;}
static void emux_get_int_1(int s,int*out,int u){*out=1541;}
#define FILE FakeFile
#define fopen fake_open
#define ferror fake_error
#define fflush fake_flush
#define fclose fake_close
#define fprintf fake_print
#define BMC64_NEW_KEYBOARD_INPUT 1
#define BMC64_MACHINE_CLASS_C128 2
#define MAX_USB_DEVICES 4
#define MAX_USB_BUTTONS 32
#define NUM_GPIO_PINS 32
#define Setting_DriveNType 0
struct item {int value,choice_ints[4],layout,mapping;char str_value[64];};
static struct item zero;
static struct item *keyboard_layout_mapping_item=&zero;
static int emux_machine_class=0,saved_network_device,network_reboot_prompted,saved_webui_enabled,webui_reboot_prompted;
static char saved_webui_pin[64];
static int usb_pref[4],usb_x_axis[4],usb_y_axis[4],usb_button_assignments[4][32];
static float usb_x_thresh[4],usb_y_thresh[4];
static int acia_network_addresses[4],keyset_codes[2][16],key_bindings[6],gpio_bindings[32];
static int pot_x_high_value,pot_x_low_value,pot_y_high_value,pot_y_low_value;
"""
for i,name in enumerate(['UP','DOWN','LEFT','RIGHT','FIRE','POTX','POTY']):menu_save+=f'#define KEYSET_{name} {i}\n'
arrays=set(re.findall(r'(\w+)\[\d\]->',save_body))
for name in arrays:menu_save+=f'static struct item *{name}[2]={{&zero,&zero}};\n'
for name in set(re.findall(r'(\w+)->',save_body))-arrays:menu_save+=f'static struct item *{name}=&zero;\n'
menu_save+=function(menu_source,'finish_settings_file')+save_body+r"""
static void reset(void){output.error=0;open_bad=write_bad=flush_bad=close_bad=emux_bad=emux_calls=closed=logged=0;}
int main(void){reset();CHECK(save_settings_to("x","v")==0&&closed==1&&logged==1&&emux_calls==1);
 reset();open_bad=1;CHECK(save_settings_to("x","v")==1&&emux_calls==1&&closed==0);
 reset();emux_bad=close_bad=1;CHECK(save_settings_to("x","v")==1&&errno==EIO&&closed==0&&logged==0);
 reset();write_bad=close_bad=1;CHECK(save_settings_to("x","v")==1&&errno==ENOSPC&&closed==1&&logged==0);
 reset();flush_bad=close_bad=1;CHECK(save_settings_to("x","v")==1&&errno==EIO&&closed==1&&logged==0);
 reset();close_bad=1;CHECK(save_settings_to("x","v")==1&&errno==EROFS&&logged==0);
 printf("PASS: %d production native settings-save caller fault/success checks\n",count);return 0;}
"""
# Every audited settings writer is wired to the tested finalization helper.
menu=(root/'third_party/common/menu.c').read_text()
for name in ['save_settings_to','save_wifi_settings','save_network_menu']:
    assert 'finish_settings_file(fp)' in function(menu,name),name
assert 'if (read_error)' in function(menu,'list_files')
with tempfile.TemporaryDirectory(prefix='e64-fs-stage1-') as tmp:
    run(tmp,'libc',core,True)
    run(tmp,'sdk',sdk)
    run(tmp,'traversal',traversal)
    run(tmp,'stdio',stdio)
    run(tmp,'resources',resource)
    run(tmp,'ioutil',ioutil)
    run(tmp,'menu_save',menu_save)
print('PASS: Stage 1 fault injection; underlying synchronization implementation is unchanged.')
