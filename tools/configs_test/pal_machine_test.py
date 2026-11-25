#!/usr/bin/env python3
"""Run production machine parser, application, menu selection and boot fallback."""
from pathlib import Path
import re, subprocess, tempfile
root = Path(__file__).resolve().parents[2]
def function(path, name):
    s=(root/path).read_text()
    m=re.search(r'^(?:static )?[\w:* ]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M)
    assert m,name
    return s[m.start():s.index('\n}',m.end())+2]
prepared=root/'templates/e64-v1/system/machines.txt'
assert b'[C64/PAL/HDMI/' in prepared.read_bytes()
header=(root/'third_party/common/menu_switch.h').read_text().replace('#include "emux_api.h"','typedef enum {BMC64_MACHINE_CLASS_UNKNOWN, BMC64_MACHINE_CLASS_VIC20, BMC64_MACHINE_CLASS_C64, BMC64_MACHINE_CLASS_C128, BMC64_MACHINE_CLASS_PLUS4, BMC64_MACHINE_CLASS_PLUS4EMU, BMC64_MACHINE_CLASS_PET} BMC64MachineClass;')
switch=(root/'third_party/common/menu_switch.c').read_text()
switch=re.sub(r'^#include .*$', '', switch, flags=re.M)
code=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <unistd.h>
#include <assert.h>
#include "configs_internal.h"
#include "sd_fs.h"
static const char *card;
static int fail_machine_open;
static const char *machine_source;
static FILE *card_open(const char *p,const char *m) {
 char path[1024];
 if(fail_machine_open && !strcmp(p,"/system/machines.txt"))return NULL;
 if(machine_source && !strcmp(p,"/system/machines.txt"))return fopen(machine_source,m);
 snprintf(path,sizeof(path),"%s%s",card,p);return fopen(path,m);
}
static int card_unlink(const char *p) {
 char path[1024];snprintf(path,sizeof(path),"%s%s",card,p);return unlink(path);
}
static int circle_get_model(void){return 3;}
static int fan_dpi_allowed(void){return 1;} /* generic shared-library fixture */
#define fopen card_open
#define unlink card_unlink
'''+header+switch+r'''
#undef fopen
#undef unlink
enum {MACHINE_TIMING_NTSC_CUSTOM_HDMI=11, MACHINE_TIMING_PAL_CUSTOM_HDMI=12};
static int mock_timing=11, mock_cycles=1022736;
static int circle_get_machine_timing(void){return mock_timing;}
static int circle_cycles_per_sec(void){return mock_cycles;}
static int booted_ntsc=1;
static BMC64VideoOut booted_out=BMC64_VIDEO_OUT_HDMI;
static int rebooted;
static int describe_pal;
static void fan_prepare_shutdown(void){}
static void reboot(void){rebooted++;}
#define ui_error(...) ((void)0)
static char start_error[64];
'''+function('third_party/common/menu_configs.c','apply_machine')+'\n'+function('third_party/common/menu_configs.c','menu_configs_start')+r'''
const char *circle_get_disk_volume(void){return "SD";}
static int config_assets_in_use(const char *id){(void)id;return 0;}
static void describe_booted(const char *machine,char *out,int size){snprintf(out,size,"%s/%s/HDMI",machine,describe_pal?"PAL":"NTSC");booted_ntsc=!describe_pal;}
'''+function('third_party/common/menu_configs.c','menu_configs_boot')+r'''
static void put(const char *p,const char *s){assert(sd_write_file(p,s,strlen(s))==SD_OK);}
static void has(const char *p,const char *s){char b[8192];assert(sd_read_file(p,b,sizeof(b))>0);if(!strstr(b,s)){fprintf(stderr,"Missing %s in %s:\n%s\n",s,p,b);abort();}}
int main(int argc,char **argv){
 assert(argc==3);card=argv[1];setenv("SD_TEST_ROOT",card,1);
 configs_boot_init("C64/NTSC/HDMI");
 assert(configs_machine_covers("C64/NTSC",configs_factory_info(0)->machine));
 assert(configs_machine_covers("C64/PAL",configs_factory_info(1)->machine));
 assert(sd_mkdir("/configs")==SD_OK);
 assert(sd_mkdir("/configs/user")==SD_OK);
 put("/configs/user/config.txt","name=User\nmachine=C64/NTSC/HDMI\n");
 put("/configs/user/settings.txt","palette=4\n");
 put("/configs/user/vice.ini","KernalName=custom\n");
 assert(configs_switch_to(CONFIGS_FACTORY_NTSC)==CONFIGS_OK);
 configs_boot_init("C64/NTSC/HDMI");
 // Missing definition must neither persist PAL nor mutate boot files.
 char before[4096],after[4096];int n=sd_read_file("/config.txt",before,sizeof(before));assert(n>0);
 machine_source=argv[2];menu_configs_start(CONFIGS_FACTORY_PAL,0);
 assert(!rebooted && strstr(start_error,"No machine"));
 assert(sd_read_file("/config.txt",after,sizeof(after))==n&&!memcmp(before,after,n));
 configs_boot_init("C64/NTSC/HDMI");assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 // Failed file application must not select PAL either.
 machine_source=NULL;fail_machine_open=1;
 menu_configs_start(CONFIGS_FACTORY_PAL,0);assert(!rebooted&&*start_error);
 fail_machine_open=0;assert(sd_rename("/config.txt","/config.saved")==SD_OK);
 menu_configs_start(CONFIGS_FACTORY_PAL,0);assert(!rebooted&&*start_error);
 assert(sd_rename("/config.saved","/config.txt")==SD_OK);
 configs_boot_init("C64/NTSC/HDMI");assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 menu_configs_start(CONFIGS_FACTORY_PAL,0);assert(rebooted==1&&!*start_error);
 has("/config.txt","hdmi_group=1\n");has("/config.txt","hdmi_mode=19\n");
 has("/config.txt","sdtv_mode=18\n");
 sd_read_file("/config.txt",after,sizeof(after));assert(!strstr(after,"hdmi_timings="));
 has("/cmdline.txt","machine_timing=pal-hdmi");has("/cmdline.txt","audio_out=hdmi");
 configs_boot_init("C64/PAL/HDMI");assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_PAL));
 configs_boot_init("C64/PAL/HDMI");assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_PAL));
 booted_ntsc=0;menu_configs_start(CONFIGS_FACTORY_NTSC,0);assert(rebooted==2&&!*start_error);
 has("/config.txt","hdmi_group=2\n");has("/config.txt","hdmi_mode=87\n");
 has("/config.txt","hdmi_timings=768 0 24 72 96 525 1 3 10 9 0 0 0 60 0 31416828 1");
 has("/cmdline.txt","machine_timing=ntsc-custom");has("/cmdline.txt","cycles_per_second=1022736");
 has("/cmdline.txt","audio_out=hdmi");

 // Calibration metadata: independent standards and Configs; validation and
 // transactional persistence through rename, reboot and machine switching.
 assert(configs_save_timing("user",1,1022001)==CONFIGS_OK);
 assert(configs_save_timing("user",0,982800)==CONFIGS_OK);
 assert(configs_save_timing("user",1,0)==CONFIGS_ERROR);
 assert(configs_save_timing("user",1,2500001)==CONFIGS_ERROR);
 assert(configs_save_timing(CONFIGS_FACTORY_NTSC,1,1022001)==CONFIGS_ERROR);
 assert(configs_save_timing(CONFIGS_FACTORY_PAL,0,982800)==CONFIGS_ERROR);
 assert(configs_switch_to("user")==CONFIGS_OK);
 configs_boot_init("C64/NTSC/HDMI");
 assert(configs_running_timing(1)==1022001 && configs_running_timing(0)==982800);
 assert(configs_rename_running("Calibrated")==CONFIGS_OK);
 configs_boot_init("C64/NTSC/HDMI");
 assert(configs_running_timing(1)==1022001 && configs_running_timing(0)==982800);
 // Protection blocks a save and preserves the old measurements.
 assert(configs_set_protected("user",1,0)==CONFIGS_OK);
 assert(configs_save_timing("user",1,1022002)==CONFIGS_ERROR);
 assert(configs_set_protected("user",0,1)==CONFIGS_OK);
 // Boot timing synchronization preserves network/audio and HDMI bytes.
 put("/cmdline.txt","# timing test\nnetwork=1 hostname=e64 audio_out=hdmi flag machine_timing=ntsc-custom cycles_per_second=1022736\n");
 n=sd_read_file("/config.txt",before,sizeof(before));
 int prior=rebooted;
 menu_configs_boot("C64");assert(rebooted==prior+1);
 has("/cmdline.txt","cycles_per_second=1022001");
 has("/cmdline.txt","network=1 hostname=e64 audio_out=hdmi flag");
 assert(sd_read_file("/config.txt",after,sizeof(after))==n&&!memcmp(before,after,n));
 mock_cycles=1022001;
 prior=rebooted;menu_configs_boot("C64");assert(rebooted==prior);
 // Switching to an uncalibrated same-standard Config resets to machine timing.
 assert(sd_mkdir("/configs/other")==SD_OK);
 put("/configs/other/config.txt","name=Other\nmachine=C64/NTSC/HDMI\n");
 menu_configs_start("other",0);has("/cmdline.txt","cycles_per_second=1022736");
 configs_boot_init("C64/NTSC/HDMI");assert(configs_running_timing(1)==0);
 // Same-standard switch back synchronizes its own saved value.
 menu_configs_start("user",0);mock_cycles=1022736;
 prior=rebooted;menu_configs_boot("C64");assert(rebooted==prior+1);
 has("/cmdline.txt","cycles_per_second=1022001");

 // Start Once calibration must not leak into the uncalibrated power-on Config.
 assert(configs_switch_to("other")==CONFIGS_OK);
 assert(configs_start_once("user")==CONFIGS_OK);
 mock_cycles=1022736;menu_configs_boot("C64");mock_cycles=1022001;
 menu_configs_boot("C64");configs_after_boot();
 prior=rebooted;menu_configs_boot("C64");assert(rebooted==prior+1);
 assert(!strcmp(configs_running()->id,"other"));
 has("/cmdline.txt","cycles_per_second=1022736");
 mock_cycles=1022736;prior=rebooted;menu_configs_boot("C64");assert(rebooted==prior);
 assert(configs_switch_to("user")==CONFIGS_OK);configs_boot_init("C64/NTSC/HDMI");
 // The existing Switch Machine mechanism retains both values.
 configs_machine_switched("C64/PAL/HDMI");
 assert(configs_switch_to(CONFIGS_FACTORY_NTSC)==CONFIGS_OK);
 configs_boot_init("C64/NTSC/HDMI");
 menu_configs_start("user",0);describe_pal=1;mock_timing=12;mock_cycles=985248;
 prior=rebooted;menu_configs_boot("C64");assert(rebooted==prior+1);
 has("/cmdline.txt","machine_timing=pal-custom cycles_per_second=982800");
 has("/config.txt","hdmi_mode=19\n");
 assert(configs_running_timing(1)==1022001);
 mock_cycles=982800;prior=rebooted;menu_configs_boot("C64");assert(rebooted==prior);
 menu_configs_start(CONFIGS_FACTORY_NTSC,0);describe_pal=0;mock_timing=11;mock_cycles=1022736;
 has("/cmdline.txt","cycles_per_second=1022736");
 // Normally selected PAL must still fall back when its definition is missing.
 assert(configs_switch_to(CONFIGS_FACTORY_PAL)==CONFIGS_OK);machine_source=argv[2];
 menu_configs_boot("C64");assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 machine_source=NULL;
 assert(strstr(configs_boot_message(),"Factory timing unavailable"));
 configs_boot_init("C64/NTSC/HDMI");assert(configs_running_is_factory());
 // On PAL hardware, unavailable NTSC timing must also continue on current video.
 describe_pal=1;fail_machine_open=1;configs_recovery_choice(1);
 menu_configs_boot("C64");
 assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 assert(!strcmp(configs_booted(),"C64/PAL/HDMI"));
 assert(strstr(configs_boot_message(),"current video"));
 ActiveFile fallback;assert(active_file_read(&fallback)==0);
 assert(!strcmp(fallback.config,CONFIGS_FACTORY_NTSC));
 describe_pal=0;fail_machine_open=0;
 configs_recovery_choice(1);configs_boot_init("C64/NTSC/HDMI");
 assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_NTSC));
 assert(configs_switch_to(CONFIGS_FACTORY_PAL)==CONFIGS_OK);
 configs_boot_init("C64/PAL/HDMI");
 assert(!strcmp(configs_running()->id,CONFIGS_FACTORY_PAL));
 has("/configs/user/config.txt","name=Calibrated\nmachine=C64/PAL/HDMI\n");
 has("/configs/user/settings.txt","palette=4\n");has("/configs/user/vice.ini","KernalName=custom\n");
 puts("PASS: factory NTSC/PAL mapping, custom NTSC and PAL HDMI timing, missing definition, failed switch, persistence, recovery and user storage integrity");
}
'''
(root/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root/'build',prefix='pal-test-') as tmp:
    tmp=Path(tmp);(tmp/'system').mkdir();(tmp/'system/machines.txt').write_bytes(prepared.read_bytes())
    original=tmp/'machines-ntsc-only.txt'
    original.write_bytes(prepared.read_bytes().split(b'# E64 Default PAL:',1)[0])
    assert b'[C64/PAL/' not in original.read_bytes()
    assert b'[C64/NTSC/' in original.read_bytes()
    for name in ['config.txt','cmdline.txt']:
        data=(root/'sdcard'/name).read_bytes()
        if name == 'cmdline.txt':
            lines=data.splitlines(keepends=True)
            if b'audio_out=' not in lines[0]:
                lines[0]=lines[0].rstrip(b'\r\n')+b' audio_out=hdmi\n'
            data=b''.join(lines)
        (tmp/name).write_bytes(data)
    (tmp/'test.c').write_text(code)
    subprocess.run(['cc','-std=gnu11','-w','-I'+str(root/'src/configs'),'-I'+str(root/'src/sdcard'),str(tmp/'test.c'),str(root/'tools/sdcard/sd_fs_posix.c'),str(root/'src/sdcard/sd_fs_file.c'),*[str(p) for p in (root/'src/configs').glob('*.c')],'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test'),str(tmp),str(original)],check=True)
