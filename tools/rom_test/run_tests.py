#!/usr/bin/env python3
"""Real C64 ROM/setter/save/menu-font functions with real config lifecycle.
VICE resources, ROM lookup and hardware are replaced by host test doubles.
Fixtures are synthetic bytes, never production ROM/font assets.
"""
from pathlib import Path
import re,subprocess,tempfile
root=Path(__file__).resolve().parents[2];vice=root/'third_party/vice-3.3/src'
api=(vice/'arch/raspi/vice_api.c').read_text();rom=(vice/'c64/c64rom.c').read_text();res=(vice/'c64/c64-resources.c').read_text()
def function(text,name):
 m=re.search(r'^(?:static )?(?:int|void|const uint8_t \*)\s*'+name+r'\([^;]*?\{',text,re.M);assert m,name
 return text[m.start():text.index('\n}',m.end())+2]+'\n'
save=function(api,'emux_save_settings')
assert 'BasicName' not in save and 'ChargenName' not in save and 'KernalName' not in save
assert (root/'third_party/common/menu.c').read_text().count('if (emux_handle_rom_change(item, fullpath) < 0) return;')==2
ids=sorted(set(re.findall(r'case (MENU_\w+):',function(api,'emux_handle_rom_change'))))
pre=r'''
#define main original_config_tests_main
#include "CONFIG_TEST"
#undef main
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#define C64_KERNAL_ROM_SIZE 8192
#define C64_BASIC_ROM_SIZE 8192
#define C64_CHARGEN_ROM_SIZE 4096
#define VICE_MACHINE_C64 1
#define VICE_MACHINE_VSID 2
#define VICE_MACHINE_C64DTV 3
#define C64_KERNAL_UNKNOWN -1
#define MACHINE_RESET_MODE_HARD 1
#define BMC64_NEW_KEYBOARD_INPUT 1
#define LOG_DEFAULT 0
#define LOG_ERR -1
static int machine_class=VICE_MACHINE_C64,rom_loaded,c64rom_cartkernal_active,c64rom_log;
static uint8_t menu_chargen[4096];static int menu_chargen_ready;
static uint8_t c64memrom_kernal64_rom[8192],c64memrom_kernal64_trap_rom[8192],c64memrom_basic64_rom[8192],mem_chargen_rom[4096];
#define UI_USE_COMMON_MENU_FONT 1
#define FONT_NOTDEF_INDEX 0x7f
#define BMC64_MACHINE_CLASS_C64 1
static int emux_machine_class=1,ui_startup_error_font,ui_fb_pitch=8,ui_fb_h=8,ui_fb_w=8;
static uint8_t *ui_fb,font8x8_basic[256][8];
static uint8_t *video_font,*raw_video_font,ascii_to_petscii[256];static unsigned short video_font_translate[256];
static char *kernal_rom_name,*basic_rom_name,*chargen_rom_name,*drive_name;
static const void*keyboard_preset_active=(void*)1;
static int keyboard_saved_index;
static const char*keyboard_saved_user_sym_file="keymap.vkm";
static int keyboard_apply_preset(const void*p){assert(p==(void*)1);return 0;}
static const char*vice_config_file;static int resets,errors,rom_sets,save_fail,read_fail,close_fail,trapfl=1,rev=-1;
static char error_text[512];
static void log_error(int l,const char*f,...){(void)l;(void)f;}
static int log_open(const char*n){(void)n;return 0;}
static void log_verbose(const char*f,...){(void)f;}
static void machine_trigger_reset(int type){(void)type;resets++;}
static void lib_free(void*p){free(p);}
static char *lib_stralloc(const char*s){return strdup(s);}
static int util_string_set(char**out,const char*val){if(*out&&!strcmp(*out,val))return 1;char*newname=strdup(val);free(*out);*out=newname;return 0;}
static char *util_concat(const char*first,...){char result[1024]="";const char*s=first;va_list a;va_start(a,first);while(s){strcat(result,s);s=va_arg(a,const char*);}va_end(a);return strdup(result);}
static FILE*test_fopen(const char*name,const char*mode){char full[1024];snprintf(full,sizeof(full),"%s%s",card_root,name);return fopen(full,mode);}
static size_t test_fread(void*p,size_t s,size_t n,FILE*f){if(read_fail){read_fail=0;return fread(p,s,n/2,f);}return fread(p,s,n,f);}
static int test_fclose(FILE*f){int rc=fclose(f);if(close_fail){close_fail=0;return EOF;}return rc;}
#define fopen test_fopen
#define fread test_fread
#define fclose test_fclose
static FILE*sysfile_open(const char*name,char**path,const char*mode){char p[512];if(!strncmp(name,"./",2))name+=2;if(name[0]=='/')snprintf(p,sizeof(p),"%s",name);else snprintf(p,sizeof(p),"/c64/%s",name);FILE*f=fopen(p,mode);if(path)*path=f?strdup(p):NULL;return f;}
static long util_file_length(FILE*f){long old=ftell(f);assert(fseek(f,0,SEEK_END)==0);long n=ftell(f);assert(fseek(f,old,SEEK_SET)==0);return n;}
static int resources_get_int(const char*k,int*v){*v=!strcmp(k,"VirtualDevices")?trapfl:rev;return 0;}
static int resources_set_int(const char*k,int v){if(!strcmp(k,"VirtualDevices"))trapfl=v;else rev=v;return 0;}
static int c64rom_get_kernal_chksum_id(uint16_t*s,int*i){*s=0;*i=-1;return -1;}
static int c64rom_get_basic_checksum(void){return 0;}
static int resources_get_string(const char*k,const char**out){*out=!strcmp(k,"KernalName")?kernal_rom_name:!strcmp(k,"BasicName")?basic_rom_name:!strcmp(k,"ChargenName")?chargen_rom_name:drive_name;return 0;}
static int set_kernal_rom_name(const char*,void*);
static int set_basic_rom_name(const char*,void*);
static int set_chargen_rom_name(const char*,void*);
static int resources_set_string(const char*k,const char*v){
 if(!strcmp(k,"KernalName")){rom_sets++;return set_kernal_rom_name(v,NULL);}
 if(!strcmp(k,"BasicName")){rom_sets++;return set_basic_rom_name(v,NULL);}
 if(!strcmp(k,"ChargenName")){rom_sets++;return set_chargen_rom_name(v,NULL);}
 if(!strncmp(k,"DosName",7)){util_string_set(&drive_name,v);return !strcmp(v,"missing-drive")?-1:0;}
 return 0;
}
static int resources_save(const char*given){if(save_fail)return -1;const char*p=given?given:vice_config_file?vice_config_file:"/c64/vice.ini";write_file(p,"");FILE*f=fopen(p,"w");assert(f);fprintf(f,"[C64]\n");if(strcmp(kernal_rom_name,"kernal"))fprintf(f,"KernalName=\"%s\"\n",kernal_rom_name);if(strcmp(basic_rom_name,"basic"))fprintf(f,"BasicName=\"%s\"\n",basic_rom_name);if(strcmp(chargen_rom_name,"chargen"))fprintf(f,"ChargenName=\"%s\"\n",chargen_rom_name);if(drive_name&&strcmp(drive_name,"dos1541"))fprintf(f,"DosName1541=\"%s\"\n",drive_name);return fclose(f);}
struct menu_item{int id;char str_value[256];};
typedef char*(*fullpath_func)(int,const char*);
static void ui_error(const char*f,...){errors++;va_list a;va_start(a,f);vsnprintf(error_text,sizeof(error_text),f,a);va_end(a);}
'''.replace('CONFIG_TEST',str(root/'tools/configs_test/configs_test.c'))
funcs='\n'.join(function(rom,n) for n in ['c64rom_get_menu_chargen','read_rom_image','load_menu_chargen','c64rom_load_kernal','c64rom_load_basic','c64rom_load_chargen','mem_load'])
funcs+='\n'+'\n'.join(function(res,n) for n in ['set_chargen_rom_name','set_kernal_rom_name','set_basic_rom_name'])
funcs+='\n'+'\n'.join(function(api,n) for n in ['emux_save_settings','emux_handle_rom_change'])
funcs+='\n'+function((vice/'arch/raspi/c64/videoarch_c64.c').read_text(),'set_video_font')
funcs+='\n'+function((root/'third_party/common/ui.c').read_text(),'ui_draw_char')
tests=r'''
static void make_rom(const char*name,unsigned n,int value){char p[512];snprintf(p,sizeof(p),"/c64/%s",name);write_file(p,"");FILE*f=fopen(p,"wb");assert(f);for(unsigned i=0;i<n;i++)fputc(value,f);assert(fclose(f)==0);}
static void defaults(void){rom_loaded=0;menu_chargen_ready=0;c64rom_cartkernal_active=0;resources_set_string("KernalName","kernal");resources_set_string("BasicName","basic");resources_set_string("ChargenName","chargen");util_string_set(&drive_name,"dos1541");}
static int boot(void){configs_boot_init("C64/PAL/HDMI");vice_config_file=configs_vice_config();defaults();const char*p=vice_config_file?vice_config_file:"/c64/vice.ini";FILE*f=fopen(p,"r");char line[512];if(f){int active=0;while(fgets(line,sizeof(line),f)){line[strcspn(line,"\r\n")]=0;if(line[0]=='['){active=!strcmp(line,"[C64]");continue;}if(active){char*v=strchr(line,'=');if(v){*v++=0;if(*v=='\"'){v++;char*end=strrchr(v,'\"');if(end)*end=0;}assert(resources_set_string(line,v)==0);}}}fclose(f);}int rc=mem_load();if(rc==0)set_video_font();return rc;}
static int choose(int id,const char*name){struct menu_item item={.id=id};snprintf(item.str_value,sizeof(item.str_value),"%s",name);return emux_handle_rom_change(&item,NULL);}
static void selected(const char*k,const char*b,const char*c){assert(!strcmp(kernal_rom_name,k)&&!strcmp(basic_rom_name,b)&&!strcmp(chargen_rom_name,c));}
static void save_unchanged(void){uint8_t k[8192],b[8192],c[4096],font[4096];memcpy(k,c64memrom_kernal64_rom,sizeof(k));memcpy(b,c64memrom_basic64_rom,sizeof(b));memcpy(c,mem_chargen_rom,sizeof(c));memcpy(font,c64rom_get_menu_chargen(),sizeof(font));int reset_before=resets,sets_before=rom_sets;keyboard_preset_active=NULL;assert(emux_save_settings(configs_vice_config())==0);keyboard_preset_active=(void*)1;assert(emux_save_settings(configs_vice_config())==0);assert(resets==reset_before&&rom_sets==sets_before);assert(!memcmp(k,c64memrom_kernal64_rom,sizeof(k))&&!memcmp(b,c64memrom_basic64_rom,sizeof(b))&&!memcmp(c,mem_chargen_rom,sizeof(c))&&!memcmp(font,c64rom_get_menu_chargen(),sizeof(font)));}
int main(void){assert(original_config_tests_main()==0);char tmp[]="/tmp/e64-rom-config-XXXXXX";assert(mkdtemp(tmp));snprintf(card_root,sizeof(card_root),"%s",tmp);setenv("SD_TEST_ROOT",tmp,1);
 make_rom("kernal",8192,0x11);make_rom("basic",8192,0x22);make_rom("chargen",4096,0x33);make_rom("jiffy",8192,0x44);make_rom("custom-basic",8192,0x55);make_rom("custom-font",4096,0x66);make_rom("header-kernal",8194,0x77);
 assert(boot()==0);assert(emux_save_settings(NULL)<0);make_config("rom-test","name=ROM Test\nmachine=C64\n");assert(configs_switch_to("rom-test")==CONFIGS_OK);assert(boot()==0);selected("kernal","basic","chargen");assert(raw_video_font!=mem_chargen_rom&&video_font==raw_video_font+0x800);save_unchanged();assert(boot()==0);selected("kernal","basic","chargen");
 assert(choose(MENU_KERNAL_FILE,"jiffy")==0);assert(choose(MENU_BASIC_FILE,"custom-basic")==0);assert(choose(MENU_CHARGEN_FILE,"custom-font")==0);set_video_font();assert(mem_chargen_rom[0]==0x66&&raw_video_font[0]==0x33);selected("jiffy","custom-basic","custom-font");save_unchanged();assert(boot()==0);selected("jiffy","custom-basic","custom-font");assert(mem_chargen_rom[0]==0x66&&raw_video_font[0]==0x33);
 const int ids[]={MENU_KERNAL_FILE,MENU_BASIC_FILE,MENU_CHARGEN_FILE};const unsigned sizes[]={8192,8192,4096};
 for(int t=0;t<3;t++)for(int bad=0;bad<5;bad++){
  make_rom("short",sizes[t]-1,0x99);make_rom("long",sizes[t]+1,0x99);make_rom("valid-candidate",sizes[t],0x99);
  uint8_t k[8192],b[8192],c[4096],font[4096];memcpy(k,c64memrom_kernal64_rom,sizeof(k));memcpy(b,c64memrom_basic64_rom,sizeof(b));memcpy(c,mem_chargen_rom,sizeof(c));memcpy(font,raw_video_font,sizeof(font));
  int resets_before=resets,errors_before=errors;const char*name=bad==0?"missing":bad==1?"short":bad==2?"long":"valid-candidate";if(bad==3)read_fail=1;if(bad==4)close_fail=1;
  assert(choose(ids[t],name)<0);assert(errors==errors_before+1&&strstr(error_text,name));assert(resets==resets_before&&trapfl==1);selected("jiffy","custom-basic","custom-font");assert(!memcmp(k,c64memrom_kernal64_rom,sizeof(k))&&!memcmp(b,c64memrom_basic64_rom,sizeof(b))&&!memcmp(c,mem_chargen_rom,sizeof(c))&&!memcmp(font,raw_video_font,sizeof(font)));
 }
 c64rom_cartkernal_active=1;assert(choose(MENU_KERNAL_FILE,"header-kernal")<0);selected("jiffy","custom-basic","custom-font");c64rom_cartkernal_active=0;
 assert(choose(MENU_KERNAL_FILE,"header-kernal")==0&&c64memrom_kernal64_rom[0]==0x77);assert(choose(MENU_KERNAL_FILE,"jiffy")==0);
 int reset_before=resets;assert(choose(MENU_KERNAL_FILE,"jiffy")==0&&resets==reset_before);
 assert(choose(MENU_DRIVE_ROM_FILE_1541,"jiffy-drive")==0);assert(choose(MENU_DRIVE_ROM_FILE_1541,"missing-drive")<0&&!strcmp(drive_name,"jiffy-drive"));save_unchanged();
 save_fail=1;assert(emux_save_settings(NULL)<0);selected("jiffy","custom-basic","custom-font");save_fail=0;
 make_config("standard","name=Standard\nmachine=C64\n");make_config("geos","name=GEOS\nmachine=C64\n");
 assert(configs_switch_to("standard")==CONFIGS_OK);assert(boot()==0);selected("kernal","basic","chargen");save_unchanged();char standard_ini[4096];strcpy(standard_ini,read_file("/configs/standard/vice.ini"));
 assert(configs_switch_to("geos")==CONFIGS_OK);assert(boot()==0);assert(choose(MENU_KERNAL_FILE,"jiffy")==0&&choose(MENU_BASIC_FILE,"custom-basic")==0&&choose(MENU_CHARGEN_FILE,"custom-font")==0);save_unchanged();char geos_ini[4096];strcpy(geos_ini,read_file("/configs/geos/vice.ini"));
 for(int n=0;n<3;n++){assert(configs_switch_to("standard")==CONFIGS_OK&&boot()==0);selected("kernal","basic","chargen");assert(configs_switch_to("geos")==CONFIGS_OK&&boot()==0);selected("jiffy","custom-basic","custom-font");assert(raw_video_font[0]==0x33&&mem_chargen_rom[0]==0x66);}
 assert(!strcmp(standard_ini,read_file("/configs/standard/vice.ini"))&&!strcmp(geos_ini,read_file("/configs/geos/vice.ini")));
 make_config("clone","name=Clone\nmachine=C64\n");const char*active_ini=vice_config_file;assert(emux_save_settings("/configs/clone/vice.ini")==0);assert(vice_config_file==active_ini&&!strcmp(configs_running()->id,"geos"));selected("jiffy","custom-basic","custom-font");assert(!strcmp(geos_ini,read_file("/configs/geos/vice.ini")));
 assert(configs_switch_to("clone")==CONFIGS_OK&&boot()==0);selected("jiffy","custom-basic","custom-font");assert(configs_switch_to("geos")==CONFIGS_OK&&boot()==0);
 assert(configs_start_once("standard")==CONFIGS_OK&&boot()==0);selected("kernal","basic","chargen");configs_after_boot();assert(boot()==0);selected("jiffy","custom-basic","custom-font");
 // A missing saved ROM fails boot without rewriting the saved selection.
 char full[1024];snprintf(full,sizeof(full),"%s/c64/custom-font",card_root);assert(remove(full)==0);assert(boot()<0);selected("jiffy","custom-basic","custom-font");assert(!strcmp(geos_ini,read_file("/configs/geos/vice.ini")));make_rom("custom-font",4096,0x66);assert(boot()==0);
 // Stock CHARGEN is an explicit menu dependency, never substituted by custom.
 snprintf(full,sizeof(full),"%s/c64/chargen",card_root);assert(remove(full)==0);assert(boot()<0);assert(c64rom_get_menu_chargen()==NULL);selected("jiffy","custom-basic","custom-font");
 // Real pixel renderer: ordinary C64 text uses ROM; terminal diagnostics can
 // render with no ROM loaded. This switch is never set by a normal menu.
 uint8_t pixels[64]={0};ui_fb=pixels;ui_startup_error_font=0;raw_video_font=menu_chargen;
 memset(menu_chargen,0x33,sizeof(menu_chargen));ui_draw_char('A',0,0,9,NULL,0,1,1);assert(pixels[0]==0&&pixels[2]==9);
 memset(pixels,0,sizeof(pixels));raw_video_font=NULL;font8x8_basic['A'][0]=0x80;ui_startup_error_font=1;ui_draw_char('A',0,0,9,NULL,0,1,1);assert(pixels[0]==9&&pixels[2]==0);
 free(kernal_rom_name);free(basic_rom_name);free(chargen_rom_name);free(drive_name);remove_tree(tmp);
 puts("PASS: default/custom/Jiffy ROMs; optional header; missing/short/oversized/partial-read/close failures; no save-time ROM mutations; stable stock menu font; drive-ROM rollback; config isolation, Start Once and simulated reboot restoration.");return 0;}
'''
code=pre+'\nenum {'+','.join(ids)+'};\n'+funcs+tests
with tempfile.TemporaryDirectory(prefix='e64-rom-host-') as tmp:
 c=Path(tmp)/'test.c';c.write_text(code);exe=Path(tmp)/'test'
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-variable','-fsanitize=undefined','-g','-I'+str(root/'src/configs'),str(c),str(root/'tools/sdcard/sd_fs_posix.c'),str(root/'src/sdcard/sd_fs_file.c')]+[str(p) for p in (root/'src/configs').glob('*.c')]+['-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Host tests use synthetic ROM fixtures and mocked VICE resource storage/ROM lookup; production loaders, setters, save handler, font wiring and config lifecycle code execute unchanged.')
