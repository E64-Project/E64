#!/usr/bin/env python3
"""Execute production native listing, metadata cache, sorting and label sizing.
FatFs fixtures are in memory: no SD/USB access and no file contents are opened.
"""
from pathlib import Path
import re,subprocess,tempfile,json,random,shutil
R=Path(__file__).resolve().parents[2]
def read(p):return (R/p).read_text()
def fn(s,n):
 m=re.search(r'^(?:(?:extern "C"|static) )?[\w *]+\b'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 return s[m.start():s.index('\n}',m.end())+2]
menu=read('third_party/common/menu.c');ui=read('third_party/common/ui.c');io=read('src/new_io.cpp');sort=read('third_party/common/raspi_util.c')
code=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <strings.h>
#include <cstdint>
#include <cerrno>
#include <vector>
#include <map>
#include <set>
#include <string>
#include "ui.h"
#include "menu_theme.h"
#define NUM_DIR_TYPES 7
enum DirType {DIR_ROOT,DIR_DISKS,DIR_TAPES,DIR_CARTS,DIR_SNAPS,DIR_ROMS,DIR_IEC};
enum FileFilter {FILTER_NONE,FILTER_DISK,FILTER_CART,FILTER_TAPE,FILTER_SNAP,FILTER_DIRS,FILTER_PRGS,FILTER_IDE64};
enum {MENU_SUB_PICK_FILE=1,MENU_SUB_PICK_DIR,MENU_SUB_UP_DIR,MENU_SUB_ENTER_DIR,MENU_SUB_SELECT_VOLUME,MENU_AUTOSTART_FILE=123};
static char current_dir_names[NUM_DIR_TYPES][256],current_volume_name[8],full_path_str[1024];
static char current_dir_sel[NUM_DIR_TYPES][256];static int current_dir_sel_sub_id[NUM_DIR_TYPES];
struct Entry {std::string name;uint32_t size;bool directory;};
static std::map<std::string,std::vector<Entry>> volumes;
static int reads,opens,closes,errors,read_error_at=-1;
struct dirent {char d_name[256];int d_ino,d_type;};
#define DT_DIR 2
#define DT_REG 1
#define AM_DIR 16
struct FATFS_DIR {std::vector<Entry>*entries;size_t pos;};
struct FILINFO {char fname[256];unsigned fattrib;uint32_t fsize;};
struct FakeDIR {int mOpen,mFirstRead,mEntrySizeValid;uint32_t mEntrySize;FATFS_DIR mCurrentEntry;dirent mEntry;};
#define DIR FakeDIR
struct CircleDir {};
static CircleDir dummy;static std::set<DIR*> live;
static CircleDir* FindCircleDirFromDIR(DIR *p){return live.count(p)?&dummy:nullptr;}
enum FRESULT {FR_OK,FR_NO_FILE,FR_NO_PATH,FR_EXIST,FR_DENIED,FR_LOCKED,FR_WRITE_PROTECTED,FR_INVALID_NAME,FR_INVALID_PARAMETER,FR_INVALID_OBJECT,FR_TOO_MANY_OPEN_FILES,FR_NOT_ENOUGH_CORE,FR_TIMEOUT,FR_NOT_READY,FR_NOT_ENABLED,FR_INVALID_DRIVE,FR_DISK_ERR};
static FRESULT f_readdir(FATFS_DIR *d,FILINFO *info){
 if(!info){d->pos=0;return FR_OK;}reads++;
 if(read_error_at>=0&&(int)d->pos>=read_error_at)return FR_DISK_ERR;
 if(d->pos==d->entries->size()){info->fname[0]=0;return FR_OK;}
 auto &e=(*d->entries)[d->pos++];snprintf(info->fname,sizeof(info->fname),"%s",e.name.c_str());info->fattrib=e.directory?AM_DIR:0;info->fsize=e.size;return FR_OK;
}
static void io_stats_readdir_entry(){}
static DIR *opendir(const char *path){
 opens++;auto i=volumes.find(path);if(i==volumes.end()){errno=ENOENT;return nullptr;}
 DIR *d=new DIR{};d->mOpen=1;d->mFirstRead=1;d->mCurrentEntry.entries=&i->second;live.insert(d);return d;
}
static int closedir(DIR *d){assert(live.erase(d)==1);d->mOpen=0;delete d;closes++;return 0;}
void ui_error(const char *message,...){assert(!strcmp(message,"Cannot read directory"));errors++;}
static void autostart_file_open(menu_item*){}
static std::string active_rom;
static int emux_active_drive_rom(int, char *path, unsigned capacity){snprintf(path,capacity,"%s",active_rom.c_str());return !active_rom.empty();}
static int extension(const char *s,const char *ext){const char *dot=strrchr(s,'.');return dot&&!strcasecmp(dot,ext);}
static int test_disk_name(const char *s){return extension(s,".d64");}
static int test_tape_name(const char *s){return extension(s,".tap");}
static int test_cart_name(const char *s){return extension(s,".crt");}
static int test_snap_name(const char *s){return extension(s,".vsf");}
static int test_prg_name(const char *s){return extension(s,".prg");}
static int test_ide64_name(const char *s){return extension(s,".dhd");}
'''
for source,names in [(io,['fatfs_errno','read_next_entry','do_readdir','bmc64_directory_entry_size','readdir','rewinddir']),
 (ui,['ui_utf8_next','ui_text_width','append','ui_new_item','ui_menu_add_button_with_value','ui_menu_add_button','ui_menu_add_divider','ui_add_all']),
 (sort,['sorted_merge','split','merge_sort']),
 (menu,['fullpath','remove_dir','menu_is_documentation','menu_is_rom_candidate','format_browser_size','file_label_prefix','fit_file_size_label','rom_browser_path','list_files','file_item_key','files_cursor_listener','find_file_item_pos'])]:
 for n in names:code+='\n'+fn(source,n)+'\n'
code+=r'''
static void free_rows(menu_item &root){auto p=root.first_child;while(p){auto next=p->next;free(p);p=next;}root.first_child=nullptr;}
static std::vector<menu_item*> files(menu_item &root){std::vector<menu_item*> out;for(auto p=root.first_child;p;p=p->next)if(p->sub_id==MENU_SUB_PICK_FILE)out.push_back(p);return out;}
static void layout(const menu_item *p){
 assert(strlen(p->name)<MAX_MENU_STR);
 int text_x=p->menu_left+8,right=p->menu_left+p->menu_width-8;
 int size_x=right-ui_text_width(p->displayed_value);
 assert(text_x%8==0&&size_x%8==0&&right%8==0);
 assert(text_x+ui_text_width(p->name)+8<=size_x);
}
int main(int argc,char **argv){
 if(argc>1){for(int i=1;i<argc;i++){char text[32];format_browser_size((uint32_t)strtoull(argv[i],nullptr,10),text,sizeof(text));puts(text);}return 0;}
 const std::vector<std::pair<uint32_t,std::string>> sizes={{0,"0 B"},{1,"1 B"},{1023,"1023 B"},{1024,"1 KB"},{4096,"4 KB"},{8192,"8 KB"},{16384,"16 KB"},{174848,"171 KB"},{1048576,"1.0 MB"},{10485760,"10 MB"},{1073741824,"1.00 GB"},{0xffffffffu,"4.00 GB"}};
 for(auto &e:sizes){char text[32];format_browser_size(e.first,text,sizeof(text));assert(e.second==text);}
 // Each iterator owns its last-entry metadata; getters never advance/read it.
 volumes["SD:/cache"]={{"empty.rom",0,false},{"folder",777,true},{"next.rom",4096,false}};
 volumes["USB:/cache"]={{"other.rom",16384,false}};
 DIR *a=opendir("SD:/cache"),*b=opendir("USB:/cache");uint32_t size=99;
 assert(bmc64_directory_entry_size(a,&size)<0);assert(readdir(a));assert(readdir(b));int io_reads=reads;
 assert(bmc64_directory_entry_size(a,&size)==0&&size==0);assert(bmc64_directory_entry_size(b,&size)==0&&size==16384&&reads==io_reads);
 assert(readdir(a)&&bmc64_directory_entry_size(a,&size)<0);assert(readdir(a)&&bmc64_directory_entry_size(a,&size)==0&&size==4096);
 assert(!readdir(a)&&bmc64_directory_entry_size(a,&size)<0);rewinddir(b);assert(bmc64_directory_entry_size(b,&size)<0);
 closedir(a);closedir(b);assert(bmc64_directory_entry_size(a,&size)<0);
 // Build actual lists across qualified volumes, preserving filters and parent controls.
 for(const char *volume:{"SD:","USB:","USB2:","USB3:"}){
  std::string path=std::string(volume)+"/files/";auto &entries=volumes[path];
  entries={{"z-folder",777,true},{"a-folder",1,true},{"README.txt",16,false},{"._hidden.rom",16,false}};
  for(size_t i=0;i<sizes.size();i++)entries.push_back({"file-"+std::to_string(i)+".rom",sizes[i].first,false});
  std::string prefix(30,'A');entries.push_back({prefix+"Z.rom",16384,false});entries.push_back({prefix+"B.rom",16384,false});
  entries.push_back({std::string(240,'L')+".rom",174848,false});entries.push_back({"ÉÉÉÉÉÉÉÉÉÉÉÉÉÉÉÉÉÉÉÉ.rom",16384,false});
  entries.push_back({"boot.d64",174848,false});entries.push_back({"game.prg",43008,false});
  strcpy(current_volume_name,volume);strcpy(current_dir_names[DIR_DISKS],"/files/");
  menu_item root={};root.type=FOLDER;root.menu_width=320;root.menu_height=200;root.value=DIR_DISKS;
  int before_reads=reads;list_files(&root,DIR_DISKS,FILTER_NONE,MENU_AUTOSTART_FILE);
  assert(std::string(root.first_child->name)==std::string(!strcmp(volume,"USB:")?"USB1:":volume)+"/files/");
  assert(!strcmp(current_volume_name,volume));
  assert(reads-before_reads==(int)entries.size()+1);assert(root.first_child->sub_id==MENU_SUB_UP_DIR&&root.first_child->symbol==31);
  assert(!strcmp(root.first_child->next->next->name,"a-folder")&&!strcmp(root.first_child->next->next->displayed_value,"(dir)"));
  auto found=files(root);assert(found.size()==entries.size()-4);
  int b_index=-1,z_index=-1;
  for(size_t i=0;i<found.size();i++){
   auto p=found[i];layout(p);assert(strstr(p->str_value,"README")==nullptr&&strncmp(p->str_value,"._",2));
   if(std::string(p->str_value)==prefix+"B.rom")b_index=i;
   if(std::string(p->str_value)==prefix+"Z.rom")z_index=i;
   if(strlen(p->str_value)>35)assert(std::string(p->name).substr(strlen(p->name)-4)==".rom");
   // Cached row formatting and selection do not read the filesystem.
   int held_reads=reads,held_opens=opens;int row=0;for(auto q=root.first_child;q!=p;q=q->next)row++;
   files_cursor_listener(&root,row);assert(!strcmp(current_dir_sel[DIR_DISKS],p->str_value));
   assert(find_file_item_pos(&root,DIR_DISKS)==row);
   std::string full=std::string(volume)+"/files/"+p->str_value;assert(full==fullpath(DIR_DISKS,p->str_value));
   for(int repeat=0;repeat<50;repeat++){layout(p);assert(ui_text_width(p->displayed_value)>0);}
   assert(reads==held_reads&&opens==held_opens);
  }
  assert(b_index>=0&&z_index>b_index);
  assert(!strcmp(found[b_index]->name,found[z_index]->name));
  assert(strcmp(found[b_index]->str_value,found[z_index]->str_value));
  for(auto p:found)for(const char *c=p->name;*c;){uint32_t cp;c=ui_utf8_next(c,&cp);assert(cp!=0xfffd);}
  free_rows(root);
  strcpy(current_dir_names[DIR_DISKS],"/");volumes[std::string(volume)+"/"]={};
  root.type=FOLDER;list_files(&root,DIR_DISKS,FILTER_NONE,MENU_AUTOSTART_FILE);
  assert(std::string(root.first_child->name)==std::string(!strcmp(volume,"USB:")?"USB1:":volume)+"/");
  assert(root.first_child->sub_id==MENU_SUB_SELECT_VOLUME);free_rows(root);
  strcpy(current_dir_names[DIR_DISKS],"/files/");
  // Autostart image open callbacks, ordinary filters, directory-only selection.
  for(auto filter:{FILTER_DISK,FILTER_PRGS,FILTER_DIRS}){
   root.type=FOLDER;list_files(&root,DIR_DISKS,filter,MENU_AUTOSTART_FILE);auto picked=files(root);
   if(filter==FILTER_DIRS){assert(picked.empty());bool use=false;for(auto p=root.first_child;p;p=p->next)use|=p->sub_id==MENU_SUB_PICK_DIR;assert(use);}
   else {assert(picked.size()==1);if(filter==FILTER_DISK)assert(picked[0]->on_open==autostart_file_open);}
   free_rows(root);
  }
 }
 // Active Drive ROM uses full path and retains a bounded size column.
 for(const char *volume:{"SD:","USB:"}){
  strcpy(current_volume_name,volume);strcpy(current_dir_names[DIR_ROMS],"/files/");
  volumes[std::string(volume)+"/files/"]={{"same.rom",16384,false},{std::string(220,'L')+".rom",16384,false}};
  active_rom="SD:/files/same.rom";menu_item marked={};marked.type=FOLDER;marked.menu_width=320;marked.menu_height=200;
  list_files(&marked,DIR_ROMS,FILTER_NONE,9);auto rows=files(marked);assert(rows.size()==2);int stars=0;
  for(auto row:rows){layout(row);if(strchr(row->name,'*')){stars++;assert(!strcmp(row->str_value,"same.rom"));}}
  assert(stars==(!strcmp(volume,"SD:")?1:0));free_rows(marked);
 }
 active_rom.clear();
 // Large lists: one enumeration, sizes held on menu nodes, no per-file stat.
 auto &many=volumes["USB:/many/"];for(int i=1999;i>=0;i--){char name[64];snprintf(name,sizeof(name),"file-%04d.rom",i);many.push_back({name,(uint32_t)i*1024,false});}
 strcpy(current_volume_name,"USB:");strcpy(current_dir_names[DIR_DISKS],"/many/");menu_item root={};root.type=FOLDER;root.menu_width=320;root.menu_height=200;
 int before_reads=reads;list_files(&root,DIR_DISKS,FILTER_NONE,9);assert(reads-before_reads==2001);auto all=files(root);assert(all.size()==2000);
 for(int i=0;i<2000;i++){char expected[64];snprintf(expected,sizeof(expected),"file-%04d.rom",i);assert(!strcmp(all[i]->str_value,expected));layout(all[i]);}free_rows(root);
 // Read failure clears partial results and closes the iterator as before.
 read_error_at=1;list_files(&root,DIR_DISKS,FILTER_NONE,9);assert(errors==1&&files(root).empty());free_rows(root);read_error_at=-1;
 assert(live.empty()&&opens==closes);
 puts("PASS: production native list/size cache, bytes/KB/MB/GB, SD/USB paths, directories/filters/parent controls, long UTF-8 names/extensions, stable sorting, full selection keys, 2000 entries, gap/alignment and zero filesystem access during cached row/selection work");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-native-file-sizes-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-variable','-Wno-write-strings','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)

 values=[1024,4096,8192,16384,174848,1048575,1048576,1048577,1073741823,1073741824,4294967295]
 values += [int(k*1024) for k in [10239,10240,10752,11776,1048575,1048576]]
 rng=random.Random(64);values += [rng.randrange(1024,4294967296) for _ in range(200)]
 actual=subprocess.check_output([str(exe),*[str(n) for n in values]],text=True).splitlines()
 node=shutil.which('node') or str(Path.home()/'.cache/bmc64/toolchains/node-v24.21.0-linux-x64/bin/node')
 reference="import {fmtBytes} from './src/webui/assets/js/util.js'; console.log(JSON.stringify(JSON.parse(process.argv[1]).map(fmtBytes)));"
 expected=json.loads(subprocess.check_output([node,'--input-type=module','-e',reference,json.dumps(values)],cwd=R,text=True))
 assert actual==expected,[(n,a,b) for n,a,b in zip(values,actual,expected) if a!=b]
 print('PASS:',len(values),'native size values match actual Web formatter, including boundaries, rounding ties and UINT32_MAX')

# Compare native formatter against the real Web formatter above the explicit
# sub-KB B-unit exception. Boundary and tie rounding are exercised as integers.
assert 'stat(' not in fn(menu,'list_files')
assert 'bmc64_directory_entry_size' not in ui and 'format_browser_size' not in ui
print('PASS: shared renderer untouched; list uses enumeration metadata, no per-file stat')
