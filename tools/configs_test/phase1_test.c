#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "configs_internal.h"
#include "sd_fs.h"
#include "../../src/keyboard/gpio_recovery.h"
static unsigned us, scans, row_restore;
static int active_row=-1, mode, bounce;
static void row(void *ctx,unsigned pa,int low) {
 (void)ctx;
 if(mode&32)us+=10;
 if(low){assert(pa==7);assert(active_row<0);active_row=(int)pa;}
 else{assert(active_row==(int)pa);active_row=-1;row_restore++;}
}
static int read_key(void *ctx,unsigned pb) {
 (void)ctx;
 int c=(mode&1)!=0;
 if((mode&64) && us>=100000)c=0;
 if(bounce && us<40000)c=(us/1000)%2;
 int down=(mode&16)||(active_row==7&&pb==5&&c)||
          (active_row==1&&pb==7&&(mode&2))||
          (active_row==6&&pb==4&&(mode&4))||
          (active_row==0&&pb==3&&(mode&8));
 scans++;return !down;
}
static void delay(void *ctx,unsigned t){(void)ctx;us+=t;}
static unsigned now(void *ctx){(void)ctx;return us;}
static void sample(int keys,int bouncing,int expected) {
 mode=keys;bounce=bouncing;us=scans=row_restore=0;
 GpioRecoveryIO io={0,row,read_key,delay,now};
 assert(gpio_recovery_sample(&io)==expected);
 assert(us==50000&&scans>=51&&row_restore>=50);
 assert(active_row==-1);
}
static int roms,ints;
static int si(const char *key,int value) {
 if(!strcmp(key,"CartridgeType"))assert(value==-1);
 else if(!strcmp(key,"SoundVolume"))assert(value==100);
 else if(!strcmp(key,"DriveSoundEmulationVolume"))assert(value==1000);
 else if(!strcmp(key,"DriveSoundEmulation"))assert(value==1);
 else if(strstr(key,"AutoType"))assert(value==1);
 else assert(value==0);
 ints++;return 0;
}
static int ss(const char *key,const char *value) {
 if(!strcmp(key,"BasicName"))assert(!strcmp(value,"basic"));
 else if(!strcmp(key,"KernalName"))assert(!strcmp(value,"kernal"));
 else if(!strcmp(key,"ChargenName"))assert(!strcmp(value,"chargen"));
 else {assert(!strcmp(key,"CartridgeFile"));assert(!*value);}
 roms++;return 0;
}
static void put(const char *path,const char *text){assert(sd_write_file(path,text,(int)strlen(text))==SD_OK);}
static void same(const char *path,const char *text){char b[4096];assert(sd_read_file(path,b,sizeof(b))==(int)strlen(text));assert(!strcmp(b,text));}
static void factory(const char *id) {
 assert(configs_switch_to(id)==CONFIGS_OK);
 configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,id));
 assert(configs_running_is_factory());
 const char *baseline[]={"h_center_0=0\n","v_center_0=0\n","h_border_0=32\n",
  "v_border_0=20\n","h_stretch_0=1600\n","v_stretch_0=1000\n",
  "scaling_interp=0\n","use_int_scaling_0=0\n","volume=100\n"};
 for(unsigned i=0;i<sizeof(baseline)/sizeof(*baseline);i++)
  assert(strstr(configs_factory_settings(),baseline[i]));
 roms=ints=0;assert(configs_factory_resources(si,ss)==0&&roms==4&&ints==10);
 assert(strstr(configs_factory_settings(),"palette=11\n"));
 // A session's palette edits have no persistent factory backing: every boot
 // retrieves the same firmware settings, even when saved settings exist.
 assert(configs_is_protected(id));
 assert(configs_set_protected(id,0,1)==CONFIGS_ERROR);
 assert(configs_delete(id)==CONFIGS_ERROR);
 assert(configs_rename_running("renamed")==CONFIGS_ERROR);
 assert(configs_set_autostart("SD:/bad.prg")==CONFIGS_ERROR);
 assert(configs_set_startup_disks(0)==CONFIGS_ERROR);
 ConfigFile pf;assert(config_file_read(id,&pf)==CONFIGS_OK);
 assert(config_file_write(id,&pf)==CONFIGS_ERROR);
 for(int d=0;d<4;d++)assert(!*configs_startup_disk(d));
 assert(!*configs_autostart());
 configs_after_boot();configs_boot_init("C64/NTSC/HDMI");
 assert(!strcmp(configs_running()->id,id));
 assert(configs_start_once(id)==CONFIGS_OK);
 ActiveFile af;assert(active_file_read(&af)==CONFIGS_OK);
 assert(!strcmp(af.config,id)&&!strcmp(af.once,id));
 // Factory Start Once leaves the persistent Config untouched, including
 // internal restart, consumption after successful boot, and next power-on.
 configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,id));
 configs_before_reboot();
 assert(active_file_read(&af)==CONFIGS_OK&&!strcmp(af.once,id));
 configs_after_boot();
 assert(active_file_read(&af)==CONFIGS_OK&&!af.once[0]);
 configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,id));
}
int main(void) {
 sample(0,0,0);sample(1,0,1);sample(3,0,1);sample(5,0,1);
 sample(33,0,1);sample(35,0,1);
 sample(7,0,1);sample(2,0,0);sample(4,0,0);
 sample(1,1,0);sample(9,0,1);sample(11,0,1);sample(8,0,0);sample(73,0,1);
 mode=3;bounce=0;us=0xfffff000U;scans=row_restore=0;
 GpioRecoveryIO wrap={0,row,read_key,delay,now};
 assert(gpio_recovery_sample(&wrap)==1 && us-0xfffff000U==50000);
 mode=16;us=scans=row_restore=0;GpioRecoveryIO blocked={0,row,read_key,delay,now};
 assert(gpio_recovery_sample(&blocked)==0&&us==0&&row_restore==0);
 char dir[]="/tmp/e64-phase1-XXXXXX";assert(mkdtemp(dir));assert(!setenv("SD_TEST_ROOT",dir,1));
 configs_boot_init("C64/PAL/HDMI");
 assert(sd_mkdir("/configs")==SD_OK);assert(sd_mkdir("/configs/user")==SD_OK);
 put("/configs/user/config.txt","name=User\nmachine=C64/PAL/HDMI\n");
 put("/configs/user/settings.txt","palette=4\nlegacy user settings\n");
 put("/configs/user/vice.ini","[C64]\nKernalName=custom\n");
 put("/configs/user/vice.ini.bak","untouched backup\n");
 assert(configs_switch_to("user")==CONFIGS_OK);configs_boot_init("C64/PAL/HDMI");
 configs_after_boot();same("/configs/user/settings.txt","palette=4\nlegacy user settings\n");
 // Persist NTSC, then perform repeated no-key startup through the real sampler
 // and production Config loader. This is a host boot-selection regression,
 // not proof that firmware/video reaches BASIC on physical hardware.
 assert(configs_switch_to(CONFIGS_FACTORY_NTSC)==CONFIGS_OK);
 for(int boot=0;boot<3;boot++) {
  mode=bounce=0;us=scans=row_restore=0;
  GpioRecoveryIO normal={0,row,read_key,delay,now};
  int choice=gpio_recovery_sample(&normal);assert(choice==0);
  configs_recovery_choice(choice);configs_boot_init("C64/NTSC/HDMI");
  assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
  assert(!configs_boot_message()[0]);
  ActiveFile active;assert(active_file_read(&active)==CONFIGS_OK);
  assert(!strcmp(active.config,CONFIGS_FACTORY_NTSC)&&!*active.once);
  configs_after_boot();
 }
 // Both Shift keys held continuously with C= can only recover NTSC.
 for(int keys=3;keys<=7;keys+=2) {
  assert(configs_switch_to(CONFIGS_FACTORY_PAL)==CONFIGS_OK);
  mode=keys;bounce=0;us=scans=row_restore=0;
  GpioRecoveryIO chord={0,row,read_key,delay,now};
  int choice=gpio_recovery_sample(&chord);assert(choice==1);
  configs_recovery_choice(choice);configs_boot_init("C64/PAL/HDMI");
  assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
  configs_boot_init("C64/NTSC/HDMI");
  assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 }
 // No keys and Shift alone preserve either normal factory selection.
 for(int f=0;f<2;f++) for(int keys=0;keys<=6;keys+=2) {
  const char *id=configs_factory_info(f)->id;
  assert(configs_switch_to(id)==CONFIGS_OK);
  mode=keys;bounce=0;us=scans=row_restore=0;
  GpioRecoveryIO normal={0,row,read_key,delay,now};
  int choice=gpio_recovery_sample(&normal);assert(choice==0);
  configs_recovery_choice(choice);configs_boot_init("C64/PAL/HDMI");
  assert(!strcmp(configs_running()->id,id));
 }
 factory(CONFIGS_FACTORY_NTSC);factory(CONFIGS_FACTORY_PAL);
 // A factory Start Once must return to a distinct saved user Config.
 for(int f=0;f<2;f++) {
  const char *id=configs_factory_info(f)->id;
  assert(configs_switch_to("user")==CONFIGS_OK);
  configs_boot_init("C64/PAL/HDMI");
  assert(configs_start_once(id)==CONFIGS_OK);
  ActiveFile af;assert(active_file_read(&af)==CONFIGS_OK);
  assert(!strcmp(af.config,"user")&&!strcmp(af.once,id));
  configs_boot_init(f?"C64/PAL/HDMI":"C64/NTSC/HDMI");
  assert(!strcmp(configs_running()->id,id));
  assert(configs_running_is_factory());
  if(!f)assert(!strcmp(configs_return_machine(),"C64/PAL/HDMI"));
  configs_before_reboot();
  configs_boot_init(f?"C64/PAL/HDMI":"C64/NTSC/HDMI");
  assert(!strcmp(configs_running()->id,id));
  configs_after_boot();
  assert(active_file_read(&af)==CONFIGS_OK&&!strcmp(af.config,"user")&&!af.once[0]);
  configs_boot_init("C64/PAL/HDMI");
  assert(!strcmp(configs_running()->id,"user"));
  same("/configs/user/settings.txt","palette=4\nlegacy user settings\n");
  same("/configs/user/vice.ini","[C64]\nKernalName=custom\n");
  same("/configs/user/vice.ini.bak","untouched backup\n");
 }
 // Missing saved identity falls back safely after consuming the temporary one.
 put("/configs/active.txt","config=missing\nonce=_factory-pal\n");
 configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_PAL));
 configs_after_boot();configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 roms=ints=0;assert(configs_factory_resources(si,ss)==0&&roms==4&&ints==10);
 const char *settings=configs_factory_settings();
 assert(strstr(settings,"port_1=3\nport_2=4\n"));
 assert(strstr(settings,"keyboard_layout=1\nkeyboard_layout_mapping=1\n"));
 assert(strstr(settings,"auto_drive_type_11=1\n"));
 assert(strstr(settings,"palette=11\n"));
 const char *paths[]={"SD:/configs/_factory-ntsc/vice.ini", "0:/CONFIGS/_FACTORY-PAL./settings.txt", "/configs/x/../_factory-pal/config.txt", "/configs/_factory-pal"};
 for(unsigned i=0;i<sizeof(paths)/sizeof(*paths);i++){
  assert(!configs_protection_can_write(paths[i]));assert(!configs_protection_can_remove(paths[i]));
  assert(!configs_protection_external_allowed(paths[i],1));
  assert(!sd_open(paths[i],SD_WRITE));
 }
 assert(configs_switch_to("user")==CONFIGS_OK);configs_boot_init("C64/PAL/HDMI");
 same("/configs/user/config.txt","name=User\nmachine=C64/PAL/HDMI\n");
 same("/configs/user/vice.ini","[C64]\nKernalName=custom\n");
 same("/configs/user/vice.ini.bak","untouched backup\n");
 assert(configs_switch_to("user")==CONFIGS_OK);
 configs_recovery_choice(2);configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,"user"));
 configs_boot_init("C64/PAL/HDMI");assert(!strcmp(configs_running()->id,"user"));
 configs_recovery_choice(1);configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 // Power interruption between unlink and rename: pending verified selection recovers.
 char text[2048];int n=sd_read_file("/configs/active.txt",text,sizeof(text));assert(n>0);
 put("/configs/active.new",text);assert(sd_unlink("/configs/active.txt")==SD_OK);
 configs_boot_init("C64/PAL/HDMI");assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 assert(sd_stat("/configs/active.new",0,0)==SD_NOT_FOUND);
 // A corrupt pending file never becomes authoritative.
 assert(sd_unlink("/configs/active.txt")==SD_OK);put("/configs/active.new","config=_factory-pal\nselection_crc=00000000\n");
 configs_boot_init("C64/PAL/HDMI");assert(configs_running_is_factory());
 // Existing final selection beats interrupted staging; checksum corruption fails closed.
 assert(configs_switch_to("user")==CONFIGS_OK);put("/configs/active.new",text);
 configs_boot_init("C64/PAL/HDMI");assert(!strcmp(configs_running()->id,"user"));
 text[7]='x';put("/configs/active.txt",text);configs_boot_init("C64/PAL/HDMI");assert(configs_running_is_factory());
 // Explicit Main recovery repairs missing, incomplete, corrupt and valid selection.
 put("/configs/active.txt.bak","saved selection backup\n");
 const char *records[]={NULL,"config=user\nselection_crc=12", "config=user\nselection_crc=00000000\n", "config=user\nonce=user\n"};
 for(unsigned i=0;i<4;i++) for(int choice=0;choice<=2;choice++) {
  sd_unlink("/configs/active.txt");sd_unlink("/configs/active.new");
  if(records[i])put("/configs/active.txt",records[i]);
  configs_recovery_choice(choice);
  configs_boot_init("C64/PAL/HDMI");
  if(choice==1) {
   assert(!strcmp(configs_running()->id,configs_factory_info(choice-1)->id));
   configs_boot_init("C64/PAL/HDMI");assert(configs_running_is_factory());
   assert(strstr(configs_factory_settings(),"h_stretch_0=1600\nv_stretch_0=1000\n"));
   roms=ints=0;assert(configs_factory_resources(si,ss)==0&&roms==4&&ints==10);
  } else {
   // Ordinary startup never rewrites corruption as a deliberate recovery.
   if(records[i])same("/configs/active.txt",records[i]);
   assert(configs_running_is_factory()==(i!=3));
  }
  same("/configs/active.txt.bak","saved selection backup\n");
  same("/configs/user/config.txt","name=User\nmachine=C64/PAL/HDMI\n");
  same("/configs/user/settings.txt","palette=4\nlegacy user settings\n");
  same("/configs/user/vice.ini","[C64]\nKernalName=custom\n");
  same("/configs/user/vice.ini.bak","untouched backup\n");
 }
 puts("PASS: Phase 1 GPIO/debounce/restoration/factory/protection/persistence/audio/preservation/recovery checks");
 return 0;
}
