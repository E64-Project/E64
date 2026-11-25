#!/usr/bin/env python3
"""Global network regression, independent of timing calibration tests."""
from pathlib import Path
import re, subprocess, tempfile
root=Path(__file__).resolve().parents[2]
def function(path,name):
    s=(root/path).read_text()
    m=re.search(r'^(?:static )?[\w:* ]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M)
    assert m,name
    return s[m.start():s.index('\n}',m.end())+2]
header=(root/'third_party/common/menu_switch.h').read_text().replace('#include "emux_api.h"','typedef enum {BMC64_MACHINE_CLASS_UNKNOWN, BMC64_MACHINE_CLASS_VIC20, BMC64_MACHINE_CLASS_C64, BMC64_MACHINE_CLASS_C128, BMC64_MACHINE_CLASS_PLUS4, BMC64_MACHINE_CLASS_PLUS4EMU, BMC64_MACHINE_CLASS_PET} BMC64MachineClass;')
switch=re.sub(r'^#include .*$', '', (root/'third_party/common/menu_switch.c').read_text(),flags=re.M)
code=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <unistd.h>
#include "configs_internal.h"
#include "sd_fs.h"
#include "network_prefs.h"
static const char *card;
static FILE *card_open(const char *p,const char *m){char path[1024];snprintf(path,sizeof(path),"%s%s",card,p);return fopen(path,m);}
static int card_unlink(const char *p){char path[1024];snprintf(path,sizeof(path),"%s%s",card,p);return unlink(path);}
static int circle_get_model(void){return 3;}
static int fan_dpi_allowed(void){return 1;} /* generic shared-library fixture */
#define fopen card_open
#define unlink card_unlink
'''+header+switch+r'''
#undef fopen
#undef unlink
static int booted_ntsc=1,booted_out=BMC64_VIDEO_OUT_HDMI,reboots;
static char start_error[64];
static void fan_prepare_shutdown(void){}
static void reboot(void){reboots++;}
#define ui_error(...) ((void)0)
'''+function('third_party/common/menu_configs.c','apply_machine')+'\n'+function('third_party/common/menu_configs.c','menu_configs_start')+r'''
#define BMC64_NETWORK 1
static int mNetworkDevice,mWebUiEnabled;
static char mWebUiPin[16];
static int warnings;
static const char *GetKernelName(void){return "test";}
enum {LogWarning};
static void warning(const char *a,int b,const char *c){(void)a;(void)b;(void)c;warnings++;}
'''+function('src/viceapp.cpp','ViceStdioApp::LoadNetworkDevice').replace('void ViceStdioApp::LoadNetworkDevice','static void LoadNetworkDevice').replace('mLogger.Write','warning')+r'''

struct menu_item {int value,max_length,choice_ints[5];char str_value[64];};
static struct menu_item device_item={0,0,{0},""},web_item={0,0,{0},""},pin_item={0,15,{0},""},address_item={0,0,{0},""},baud_item={0,0,{300,1200,2400},""};
static struct menu_item *network_device_item=&device_item,*webui_enabled_item=&web_item,*webui_pin_item=&pin_item,*network_modem_address_item=&address_item,*network_modem_baud_item=&baud_item;
static int saved_network_device,saved_webui_enabled,network_reboot_prompted,webui_reboot_prompted;
static char saved_webui_pin[16];
static int acia_network_addresses[]={0,0xd700,0xde00,0xdf00,0xdf80};
static void network_field_value(struct menu_item *m,const char *v){snprintf(m->str_value,sizeof(m->str_value),"%s",v);}
static int circle_set_acia_network_address(int a){(void)a;return 1;}
static int circle_set_network_modem_baud(int b){(void)b;return 1;}
static int acia_network_address_index(int a){for(int i=0;i<5;i++)if(acia_network_addresses[i]==a)return i;return 0;}
static int network_modem_baud_index(int b){return b==300?0:b==1200?1:2;}
static int emux_machine_class=BMC64_MACHINE_CLASS_C64;
static int emux_apply_ftdi_settings(const FtdiSettings *ftdi){(void)ftdi;assert(0);return 1;}
static void load_network_menu(void){}
static void update_wifi_menu_enabled(void){}
'''+function('third_party/common/menu.c','load_global_network_prefs')+'\n'+function('third_party/common/menu.c','save_global_network_prefs')+r'''
static void put(const char *p,const char *s){assert(sd_write_file(p,s,strlen(s))==SD_OK);}
static void same(const char *p,const char *s){char b[16384];assert(sd_read_file(p,b,sizeof(b))==(int)strlen(s));assert(!strcmp(b,s));}
static void has(const char *p,const char *s){char b[16384];assert(sd_read_file(p,b,sizeof(b))>=0);assert(strstr(b,s));}
static void boot(const char *desc,int device){
 configs_boot_init(desc);booted_ntsc=strstr(desc,"NTSC")!=NULL;LoadNetworkDevice();
 assert(mNetworkDevice==device && mWebUiEnabled==1 && !strcmp(mWebUiPin,"aB12=345"));
 NetworkPrefs p;assert(!network_prefs_load(&p,NULL));assert(p.modem_base==0xde00&&p.modem_baud==1200);
 load_global_network_prefs();assert(device_item.value==device&&web_item.value==1&&!strcmp(pin_item.str_value,"aB12=345"));
 assert(address_item.value==2&&baud_item.value==1);assert(!save_global_network_prefs());
}
int main(int argc,char **argv){
 assert(argc==2);card=argv[1];assert(!setenv("SD_TEST_ROOT",card,1));
 configs_boot_init("C64/NTSC/HDMI");assert(sd_mkdir("/configs")==SD_OK);
 assert(sd_mkdir("/configs/custom-ntsc")==SD_OK);assert(sd_mkdir("/configs/custom-pal")==SD_OK);
 const char *legacy="network_device=1\nwebui_enabled=1\nwebui_pin=aB12=345\nnetwork_modem_base=56832\nnetwork_modem_baud=1200\npalette=11\n";
 put("/configs/custom-ntsc/config.txt","name=NTSC\nmachine=C64/NTSC/HDMI\n");
 put("/configs/custom-pal/config.txt","name=PAL\nmachine=C64/PAL/HDMI\n");
 put("/configs/custom-ntsc/settings-c64.txt",legacy);
 put("/configs/custom-pal/settings-c64.txt","network_device=0\nwebui_enabled=0\n");
 assert(configs_switch_to("custom-ntsc")==CONFIGS_OK);
 boot("C64/NTSC/HDMI",1);same("/configs/custom-ntsc/settings-c64.txt",legacy);
 // Credentials, IP/NTP and service configuration remain byte-for-byte global.
 put("/system/wifi-settings.conf","country=US\nnetwork={\nssid=example\npsk=private-test-key\n}\n");
 put("/system/network.cfg","MODE=STATIC\nIP=192.168.1.64\nNTP_ENABLED=YES\nNTP_SERVER=192.168.1.5\n");
 for(int device=1;device<=2;device++) {
  NetworkPrefs p;assert(!network_prefs_load(&p,NULL));p.device=device;assert(!network_prefs_save(&p));
  menu_configs_start(CONFIGS_FACTORY_PAL,0);boot("C64/PAL/HDMI",device);
  menu_configs_start(CONFIGS_FACTORY_NTSC,0);boot("C64/NTSC/HDMI",device);
  menu_configs_start("custom-pal",0);boot("C64/PAL/HDMI",device);
  menu_configs_start("custom-ntsc",0);boot("C64/NTSC/HDMI",device);
  // C= recovery intentionally selects factory NTSC and retains global networking.
  configs_recovery_choice(1);boot("C64/NTSC/HDMI",device);
  assert(configs_running_is_factory());
  menu_configs_start("custom-pal",1);boot("C64/PAL/HDMI",device);configs_after_boot();
  boot("C64/NTSC/HDMI",device);
  same("/configs/custom-ntsc/settings-c64.txt",legacy);
  same("/configs/custom-pal/settings-c64.txt","network_device=0\nwebui_enabled=0\n");
  same("/system/wifi-settings.conf","country=US\nnetwork={\nssid=example\npsk=private-test-key\n}\n");
  same("/system/network.cfg","MODE=STATIC\nIP=192.168.1.64\nNTP_ENABLED=YES\nNTP_SERVER=192.168.1.5\n");
 }
 // cmdline: preserve networking, bare flags, '=' in values, tabs, long values,
 // and no trailing newline; machine definitions cannot override global keys.
 char cmd[512];char token[151];memset(token,'a',150);token[150]=0;
 snprintf(cmd,sizeof(cmd),"network_device=2\twebui_enabled=1  wifi_token=%s=a=b audio_out=hdmi hostname=e64 flag machine_timing=ntsc-custom",token);
 put("/cmdline.txt",cmd);
 struct machine_entry *head;assert(!load_machines(&head));struct machine_entry *pal=NULL;
 for(struct machine_entry *m=head;m;m=m->next)if(m->video_standard==BMC64_VIDEO_STANDARD_PAL&&m->class==BMC64_MACHINE_CLASS_C64){pal=m;break;}
 assert(pal);struct machine_option override={"network_device","0",pal->options};pal->options=&override;
 assert(!switch_apply_files(pal));pal->options=override.next;free_machines(head);
 has("/cmdline.txt","network_device=2");has("/cmdline.txt","webui_enabled=1");
 has("/cmdline.txt",token);has("/cmdline.txt","=a=b");has("/cmdline.txt","flag");has("/cmdline.txt","audio_out=hdmi");
 assert(!switch_calibrated_timing(0,982800,NULL));has("/cmdline.txt",token);has("/cmdline.txt","network_device=2");
 int changed;assert(!switch_calibrated_timing(0,0,&changed)&&changed);has("/cmdline.txt","network_device=2");
 // Reject invalid preferences without touching the last committed settings.
 NetworkPrefs p;assert(!network_prefs_load(&p,NULL));p.device=3;assert(network_prefs_save(&p));
 assert(!network_prefs_load(&p,NULL)&&p.device==2);
 // Recover a power loss between moving the old file and promoting the new one.
 assert(sd_unlink(NETWORK_PREFS_FILE)==SD_OK);
 assert(!network_prefs_load(&p,NULL)&&p.device>=1);
 assert(!warnings);
 puts("PASS: global Ethernet/Wi-Fi/Web UI/modem preferences, read-only migration, factory/custom NTSC/PAL/Start Once/C= recovery, credentials and service files, cmdline preservation and preference recovery");
}
'''
# Wiring assertions keep Config payloads separate and factory network actions usable.
menu=(root/'third_party/common/menu.c').read_text()
for name in ['save_settings_to','load_settings']:
    body=function('third_party/common/menu.c',name)
    for key in ['network_device','webui_enabled','webui_pin','network_modem_base','network_modem_baud']:
        assert '"'+key not in body,(name,key)
assert 'load_global_network_prefs();' in menu
for marker in ['case MENU_NET_SAVE:', 'confirmation_id == MENU_NETWORK_ENABLED', 'confirmation_id == MENU_WEBUI_ENABLED']:
    chunk=menu[menu.index(marker):][:400]
    assert 'save_global_network_prefs()' in chunk and 'save_settings()' not in chunk
(root/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root/'build',prefix='global-network-') as tmp:
    tmp=Path(tmp);(tmp/'system').mkdir()
    (tmp/'system/machines.txt').write_bytes((root/'templates/e64-v1/system/machines.txt').read_bytes())
    for name in ['config.txt','cmdline.txt']:
        (tmp/name).write_bytes((root/'sdcard'/name).read_bytes())
    (tmp/'test.c').write_text(code)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Wno-sign-compare','-Wno-format-truncation','-Wno-unused-variable','-I'+str(root/'src'),'-I'+str(root/'src/configs'),'-I'+str(root/'src/sdcard'),str(tmp/'test.c'),str(root/'tools/sdcard/sd_fs_posix.c'),str(root/'src/sdcard/sd_fs_file.c'),str(root/'src/network_prefs.c'),*[str(p) for p in (root/'src/configs').glob('*.c')],'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test'),str(tmp)],check=True)
