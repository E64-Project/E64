#!/usr/bin/env python3
"""Exercise production RS-232 menu builders, callbacks and resource persistence.

The genuine historical baseline is unavailable: no byte-for-byte historical
comparison is claimed. USB hotplug/transport itself remains covered by the
separate production USB/bridge suites; this test exercises its cached UI consumer.
"""
from pathlib import Path
import re
import subprocess
import tempfile

r = Path(__file__).resolve().parents[2]
v = r / 'third_party/vice-3.3/src'
s = (v / 'arch/raspi/vice_api.c').read_text()
menu = (r / 'third_party/common/menu.c').read_text()
resources = (v / 'resources.c').read_text()


def fn(source, name):
    match = re.search(r'^(?:static )?[\w *]+\b' + re.escape(name) + r'\s*\([^;]*?\{', source, re.M)
    assert match, name
    return source[match.start():source.index('\n}', match.end()) + 2]


def compact(source):
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    return re.sub(r'"(?:\\.|[^"\\])*"|\s+',
                  lambda m: m.group() if m.group().startswith('"') else '', source)


builder = compact(fn(menu, 'build_menu'))
system = 'machine_parent=ui_menu_add_folder(root,"System");'
network = ('parent=ui_menu_add_folder(machine_parent,"Network");'
           'parent->id=MENU_NETWORKING;structmenu_item*network_folder=parent;')
serial = ('structmenu_item*rs232_folder=machine_parent;'
          'if(emux_machine_class==BMC64_MACHINE_CLASS_C64||emux_machine_class==BMC64_MACHINE_CLASS_C128)'
          'rs232_folder=ui_menu_add_folder(machine_parent,emux_machine_class==BMC64_MACHINE_CLASS_C64?"Modem & RS-232 Devices":"RS-232 Devices");')
assert builder.count(system) == builder.count(network) == builder.count(serial) == 1
assert builder.index(system) < builder.index(network) < builder.index(serial)
add_options = 'emux_add_rs232_options(rs232_folder);'
assert builder.count(add_options) == 1
modem_guard = ('if(emux_machine_class!=BMC64_MACHINE_CLASS_VIC20&&'
               'emux_machine_class!=BMC64_MACHINE_CLASS_PET&&'
               'emux_machine_class!=BMC64_MACHINE_CLASS_PLUS4&&'
               'emux_machine_class!=BMC64_MACHINE_CLASS_PLUS4EMU){'
               'child=network_modem_address_item=ui_menu_add_multiple_choice('
               'MENU_NETWORK_MODEM_ADDRESS,rs232_folder,emux_machine_class==BMC64_MACHINE_CLASS_C64'
               '?"Virtual Modem Address":"RS-232 Modem Device");')
assert modem_guard in builder
assert builder.index(modem_guard) < builder.index(add_options)
assert builder.count('ui_menu_add_multiple_choice(MENU_NETWORK_MODEM_ADDRESS,') == 1
assert 'if(emux_machine_class==BMC64_MACHINE_CLASS_VIC20)ui_menu_add_divider(network_folder);' in builder
assert ('if(emux_machine_class==BMC64_MACHINE_CLASS_VIC20){'
        'child=network_modem_baud_item=ui_menu_add_multiple_choice('
        'MENU_NETWORK_MODEM_BAUD,network_folder,"Modem Baud");') in builder
assert builder.count('ui_menu_add_multiple_choice(MENU_NETWORK_MODEM_BAUD,') == 1
save_entry = ('if(emux_machine_class==BMC64_MACHINE_CLASS_C64){'
              'ui_menu_add_button(MENU_SAVE_MODEM_SETTINGS,rs232_folder,"Save Modem Settings");'
              'ui_menu_add_read_only_heading(rs232_folder,"REBOOTS AFTER SAVING");}')
assert builder.index(modem_guard) < builder.index(add_options) < builder.index(save_entry)
joy_builder = compact(fn(s, 'emux_add_userport_joys'))
assert 'MENU_RS232' not in joy_builder and 'RsUser' not in joy_builder
assert 'emux_add_rs232_options(' not in joy_builder
assert builder.index(add_options) < builder.index('parent=ui_menu_add_folder(root,"Joyports");')
assert 'emux_add_userport_joys(parent);' in builder
assert s.count('ui_menu_add_multiple_choice(MENU_RS232_FTDI,') == 1
ui_header = (r / 'third_party/common/ui.h').read_text()
assert int(re.search(r'^#define\s+MAX_CHOICES\s+(\d+)', ui_header, re.M).group(1)) >= 18
ui_source = (r / 'third_party/common/ui.c').read_text()
assert 'if (node->on_render) node->on_render(node);' in ui_source
return_case = ui_source.split('  case ACTION_Return:', 1)[1].split('  case ACTION_Escape:', 1)[0]
assert 'if (cur->disabled) break;' in return_case
assert 'else if (cur->type == BUTTON) {\n      do_on_value_changed(' in return_case
folder_start = ui_source.index('} else if (node->type == FOLDER) {',
                               ui_source.index('if (node->on_render) node->on_render(node);'))
folder_draw = ui_source[ui_source.index('{', folder_start) + 1:
                        ui_source.index('} else if (ui_is_setting_value(node))', folder_start)]

# Execute the real, contiguous common-builder section, including machine guards
# and ordering, rather than a hand-written replacement menu implementation.
common_start = menu.index('  struct menu_item *rs232_folder = machine_parent;')
common_end = menu.index('\n  load_network_menu();', common_start)
common_builder = menu[common_start:common_end]
callback_start = menu.index('  case MENU_NETWORK_MODEM_ADDRESS:')
callback_end = menu.index('  case MENU_WIFI_SSID:', callback_start)
modem_cases = menu[callback_start:callback_end]
save_case = menu[menu.index('  case MENU_SAVE_MODEM_SETTINGS:'):menu.index('  case MENU_NET_SAVE:')]
circle_header = (r / 'third_party/common/circle.h').read_text()
address_defines = '\n'.join(re.findall(
    r'^#define CIRCLE_ACIA_NETWORK_ADDRESS_(?:DEFAULT|VALUES|LABELS) .+$', circle_header, re.M))
assert len(address_defines.splitlines()) == 3
address_declarations = menu[menu.index('static const int acia_network_addresses[]'):
                            menu.index('\n\n', menu.index('static const int acia_network_addresses[]'))]
load_prefs = compact(fn(menu, 'load_global_network_prefs'))
save_prefs = compact(fn(menu, 'save_global_network_prefs'))
assert ('if(network_modem_address_item&&circle_set_acia_network_address(p.modem_base))'
        'network_modem_address_item->value=acia_network_address_index(p.modem_base);') in load_prefs
assert ('if(network_modem_address_item)p.modem_base='
        'acia_network_addresses[network_modem_address_item->value];') in save_prefs

code = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include "rs232drv/rs232usb.h"
#include "network_prefs.h"
#include "sd_fs.h"
#include <unistd.h>
enum {MENU_RS232_FTDI=1,MENU_RS232_BAUD,MENU_RS232_PARITY,MENU_RS232_DATA_BITS,
 MENU_RS232_STOP_BITS,MENU_RS232_STATUS,MENU_NETWORK_MODEM_ADDRESS,MENU_NETWORK_MODEM_BAUD};
enum {VICE_MACHINE_C64=10,BMC64_MACHINE_CLASS_C64=10,BMC64_MACHINE_CLASS_C128,
 BMC64_MACHINE_CLASS_VIC20,BMC64_MACHINE_CLASS_PET,BMC64_MACHINE_CLASS_PLUS4,BMC64_MACHINE_CLASS_PLUS4EMU};
enum {FOLDER,BUTTON,MULTIPLE_CHOICE,DIVIDER,READ_ONLY_HEADING,MENU_SAVE_MODEM_SETTINGS};
static int machine_class=VICE_MACHINE_C64,emux_machine_class=BMC64_MACHINE_CLASS_C64;
static int selected=17,baud=2400,enabled=1,joy,parity,data_bits=8,stop_bits=1,errors,writes;
static const char *reject_resource;
static int reject_once;
static e64_rs232_usb_discovery_t cached;
static unsigned snapshot_reads;
void e64_rs232_usb_discovery(e64_rs232_usb_discovery_t *p){assert(p);++snapshot_reads;*p=cached;}
struct menu_item {int id,value,num_choices,type,disabled,prefer_str,is_expanded;
 char name[64],choices[20][64],displayed_value[64],str_value[16];int choice_ints[20],choice_disabled[20];
 struct menu_item *first_child,*next;void(*on_value_changed)(struct menu_item*),(*on_render)(struct menu_item*);};
static struct menu_item nodes[32];static unsigned count;
static struct menu_item *network_modem_address_item,*network_modem_baud_item;
static void modem_changed(struct menu_item *item);
static struct menu_item *add(struct menu_item *p,int id,const char *name,int type){
 assert(count<32);struct menu_item *n=&nodes[count++];n->id=id;n->type=type;
 assert(strlen(name)<sizeof n->name);strcpy(n->name,name);
 struct menu_item **link=&p->first_child;while(*link)link=&(*link)->next;*link=n;return n;
}
static struct menu_item *ui_menu_add_folder(struct menu_item *p,const char *n){return add(p,0,n,FOLDER);}
static struct menu_item *ui_menu_add_multiple_choice(int id,struct menu_item *p,const char *n){
 struct menu_item *item=add(p,id,n,MULTIPLE_CHOICE);
 if(id==MENU_NETWORK_MODEM_ADDRESS||id==MENU_NETWORK_MODEM_BAUD)item->on_value_changed=modem_changed;
 return item;
}
static struct menu_item *ui_menu_add_button(int id,struct menu_item *p,const char *n){return add(p,id,n,BUTTON);}
static struct menu_item *ui_menu_add_read_only_heading(struct menu_item *p,const char *n){
 struct menu_item *item=add(p,0,n,READ_ONLY_HEADING);item->disabled=1;return item;
}
static struct menu_item *ui_menu_add_divider(struct menu_item *p){return add(p,0,"",DIVIDER);}
static int *value(const char *n){
 if(!strcmp(n,"RsUserFTDI"))return &selected;
 if(!strcmp(n,"RsUserBaud"))return &baud;
 if(!strcmp(n,"RsUserEnable"))return &enabled;
 if(!strcmp(n,"UserportJoy"))return &joy;
 if(!strcmp(n,"RsUserParity"))return &parity;
 if(!strcmp(n,"RsUserDataBits"))return &data_bits;
 assert(!strcmp(n,"RsUserStopBits"));return &stop_bits;
}
static int resources_get_int(const char *n,int *p){*p=*value(n);return 0;}
/* Resource boundary double: production validation/transport has separate tests.
 * Model adapter deselection disabling the userport, and inject setter failures. */
static int resources_set_int(const char *n,int val){
 ++writes;
 if(reject_once&&reject_resource&&!strcmp(n,reject_resource)){reject_once=0;return -1;}
 if(!strcmp(n,"RsUserFTDI")){
  if(val<0||val>17)return -1;
  if(selected!=val)enabled=0;
 }
 *value(n)=val;return 0;
}
static void ui_error(const char *text){assert(text);++errors;}
static int modem_address,modem_baud=2400,modem_sets,reject_modem;
static int circle_get_acia_network_address(void){return modem_address;}
static int circle_get_network_modem_baud(void){return modem_baud;}
static int circle_set_acia_network_address(int address){++modem_sets;if(reject_modem)return 0;modem_address=address;return 1;}
static int circle_set_network_modem_baud(int rate){if(reject_modem)return 0;modem_baud=rate;return 1;}
''' + address_defines + '\n' + address_declarations + '\n' + fn(menu, 'acia_network_address_index') + '\n' + fn(menu, 'network_modem_baud_index') + r'''
static void modem_changed(struct menu_item *item){switch(item->id){
''' + modem_cases + r'''
 default:assert(0);
}}
''' + 'static const int userport_bauds[]={300,1200,2400,9600};\n' + '\n'.join(
    fn(s, name) for name in ('rs232_menu_resource', 'rs232_menu_refresh', 'emux_get_ftdi_settings',
                            'emux_apply_ftdi_settings', 'rs232_heading_refresh', 'rs232_status_refresh',
                            'rs232_menu_changed', 'emux_add_rs232_options')) + r'''
static struct menu_item system_menu,network_menu;
static void build(int machine){
 memset(nodes,0,sizeof nodes);count=0;memset(&system_menu,0,sizeof system_menu);memset(&network_menu,0,sizeof network_menu);
 strcpy(system_menu.name,"System");strcpy(network_menu.name,"Network");system_menu.first_child=&network_menu;
 network_modem_address_item=network_modem_baud_item=NULL;machine_class=emux_machine_class=machine;
 struct menu_item *machine_parent=&system_menu,*network_folder=&network_menu,*child;
''' + common_builder + r'''
}
static struct menu_item *named(struct menu_item *p,const char *name){
 for(struct menu_item *n=p->first_child;n;n=n->next){if(!strcmp(n->name,name))return n;}return NULL;
}
static struct menu_item *usb(void){
 struct menu_item *rs=named(&system_menu,"Modem & RS-232 Devices");assert(rs);
 struct menu_item *serial=named(rs,"User Port/FTDI RS-232");assert(serial);
 return serial;
}
static struct menu_item *row(int id){
 for(struct menu_item *n=usb()->first_child;n;n=n->next){if(n->id==id)return n;}assert(0);return NULL;
}
static int choice(struct menu_item *item,int val){
 for(int i=0;i<item->num_choices;++i){if(item->choice_ints[i]==val)return i;}assert(0);return -1;
}
static void choose(struct menu_item *item,int val){item->value=choice(item,val);assert(item->on_value_changed);item->on_value_changed(item);}
enum {MENU_CONFIGS_SELECT=-1};
static int ui_text_width(const char *text){return 8 * strlen(text);}
static const char *drawn[2];
static int draw_x[2],draw_count;
static void ui_draw_text(const char *text,int x,int y,int colour){
 (void)y;(void)colour;assert(draw_count<2);drawn[draw_count]=text;draw_x[draw_count++]=x;
}
static void check_heading(const char *expected){
 struct menu_item *node=usb();
 assert(node->type==FOLDER&&node->on_render==rs232_heading_refresh);
 for(int expanded=0;expanded<=1;++expanded){
  node->is_expanded=expanded;
  node->on_render(node);
  assert(!strcmp(node->displayed_value,expected));
  const int indent=2,row_left=8,row_right=320-8,y=0,colour=0;
  draw_count=0;
''' + folder_draw + r'''
  assert(draw_count==2&&!strcmp(drawn[0],expanded ? "-" : "+"));
  assert(!strcmp(drawn[1],expected)&&draw_x[1]+ui_text_width(expected)==row_right);
  assert(row_left+(indent+1)*8+ui_text_width(node->name)+8<=draw_x[1]);
 }
 node->is_expanded=0;
}
static void heading_updates(void){
 selected=0;enabled=0;baud=300;parity=0;data_bits=8;stop_bits=1;
 cached=(e64_rs232_usb_discovery_t){0};
 build(VICE_MACHINE_C64);
 check_heading("Off");
 unsigned reads=snapshot_reads;
 choose(row(MENU_RS232_FTDI),17);check_heading("300,N,8,1");
 choose(row(MENU_RS232_BAUD),1200);check_heading("1200,N,8,1");
 choose(row(MENU_RS232_PARITY),1);check_heading("1200,E,8,1");
 choose(row(MENU_RS232_DATA_BITS),7);check_heading("1200,E,7,1");
 choose(row(MENU_RS232_STOP_BITS),2);check_heading("1200,E,7,2");
 choose(row(MENU_RS232_PARITY),2);check_heading("1200,O,7,2");
 choose(row(MENU_RS232_FTDI),16);check_heading("1200,O,7,2");
 choose(row(MENU_RS232_FTDI),0);check_heading("Off");
 assert(snapshot_reads==reads);
}
static struct menu_item *network_device_item,*webui_enabled_item,*webui_pin_item;
static int saved_network_device,saved_webui_enabled,network_reboot_prompted,webui_reboot_prompted;
static char saved_webui_pin[16];
static void network_field_value(struct menu_item *item,const char *text){snprintf(item->str_value,sizeof item->str_value,"%s",text);}
static void load_network_menu(void){}
static void update_wifi_menu_enabled(void){}
''' + '\n'.join(fn(menu, name) for name in ('load_global_network_prefs',
                       'save_global_network_prefs', 'save_modem_settings')) + r'''
static int reboots;
static void menu_power_reboot(void){
 NetworkPrefs prefs;
 assert(!network_prefs_load(&prefs,NULL));
 assert(prefs.modem_base==modem_address && prefs.ftdi.baud==baud &&
        prefs.ftdi.parity==parity && prefs.ftdi.data_bits==data_bits &&
        prefs.ftdi.stop_bits==stop_bits && prefs.ftdi.adapter==selected &&
        prefs.ftdi.enabled==enabled);
 ++reboots;
}
static void save_changed(struct menu_item *item){switch(item->id){
''' + save_case + r'''
 default:assert(0);
}}
static int current_menu;
static struct menu_item *menu_cursor_item[1];
static void (*on_value_changed)(struct menu_item *) = save_changed;
''' + fn(ui_source, 'do_on_value_changed') + r'''
/* Actual resource line writer/parser, with platform resource lookup doubled. */
enum {RES_INTEGER,RES_STRING,RESERR_UNKNOWN_RESOURCE=-2,RESERR_TYPE_INVALID=-3};
typedef void *resource_value_t;
typedef struct {const char *name;int type;resource_value_t *value_ptr;
 int(*set_func_int)(int,void*);int(*set_func_string)(const char*,void*);void *param;}resource_ram_t;
static int load_int(int val,void *p){*(int*)p=val;return 0;}
static resource_ram_t resources[]={
 {"RsUserFTDI",RES_INTEGER,(void*)&selected,load_int,0,&selected},
 {"RsUserEnable",RES_INTEGER,(void*)&enabled,load_int,0,&enabled},
 {"RsUserBaud",RES_INTEGER,(void*)&baud,load_int,0,&baud},
 {"RsUserParity",RES_INTEGER,(void*)&parity,load_int,0,&parity},
 {"RsUserDataBits",RES_INTEGER,(void*)&data_bits,load_int,0,&data_bits},
 {"RsUserStopBits",RES_INTEGER,(void*)&stop_bits,load_int,0,&stop_bits}};
static resource_ram_t *lookup(const char *name){
 for(unsigned i=0;i<sizeof resources/sizeof resources[0];++i){if(!strcmp(resources[i].name,name))return &resources[i];}return NULL;
}
#define uint_to_void_ptr(val) ((void*)(intptr_t)(val))
#define vice_ptr_to_int(val) ((int)(intptr_t)(val))
#define lib_free free
#define log_error(...) ((void)0)
static char *lib_msprintf(const char *format,...){va_list args;va_start(args,format);char *text=0;assert(vasprintf(&text,format,args)>=0);va_end(args);return text;}
static int util_get_line(char *text,int size,FILE *f){if(!fgets(text,size,f))return -1;text[strcspn(text,"\r\n")]=0;return strlen(text);}
static void configs_startup_failed(void){assert(0);}
static void resources_issue_callback(resource_ram_t *item,int global){(void)item;(void)global;}
''' + '\n'.join(fn(resources, name) for name in ('string_resource_item', 'write_resource_item', 'resources_read_item_from_file')) + r'''
static void roundtrip(void){
 int expected[]={selected,enabled,baud,parity,data_bits,stop_bits};
 FILE *f=fopen("resource-roundtrip.tmp","w+");assert(f);assert(!remove("resource-roundtrip.tmp"));
 for(unsigned i=0;i<sizeof resources/sizeof resources[0];++i){write_resource_item(f,i);}
 rewind(f);selected=enabled=parity=0;baud=300;data_bits=8;stop_bits=1;
 for(unsigned i=0;i<sizeof resources/sizeof resources[0];++i){assert(resources_read_item_from_file(f)==1);}
 assert(!fclose(f));
 for(unsigned i=0;i<sizeof resources/sizeof resources[0];++i){assert(*value(resources[i].name)==expected[i]);}
}
static void layout(void){
 struct menu_item *serial=usb(),*p=serial->first_child;
 struct menu_item *parent=named(&system_menu,"Modem & RS-232 Devices");
 assert(parent&&parent->first_child==network_modem_address_item);
 assert(!strcmp(network_modem_address_item->name,"Virtual Modem Address"));
 struct menu_item *save=usb()->next;
 assert(save && save->id==MENU_SAVE_MODEM_SETTINGS && save->type==BUTTON && !save->disabled);
 assert(network_modem_address_item->next==serial && !strcmp(save->name,"Save Modem Settings"));
 struct menu_item *notice=save->next;
 assert(notice && notice->type==READ_ONLY_HEADING && notice->disabled);
 assert(!strcmp(notice->name,"REBOOTS AFTER SAVING") && !notice->next);
 assert(!strcmp(serial->name,"User Port/FTDI RS-232"));
 const int ids[]={MENU_RS232_FTDI,MENU_RS232_STATUS,MENU_RS232_BAUD,MENU_RS232_PARITY,MENU_RS232_DATA_BITS,MENU_RS232_STOP_BITS};
 const char *labels[]={"USB FTDI Adapter","USB FTDI Status","Baud Rate","Parity","Data Bits","Stop Bits"};
 for(unsigned i=0;i<6;++i){assert(p&&p->id==ids[i]&&!strcmp(p->name,labels[i]));
  assert(p->num_choices<=20);
  if(i==1){assert(p->type==BUTTON&&p->disabled&&p->prefer_str&&p->on_render==rs232_status_refresh&&!p->on_value_changed);}
  else {assert(p->on_value_changed==rs232_menu_changed&&p->on_render==rs232_menu_refresh);}
  p=p->next;
 }
 assert(!p&&count==11);
 p=row(MENU_RS232_FTDI);assert(p->num_choices==18);
 assert(!strcmp(p->choices[0],"Off")&&p->choice_ints[0]==0);
 assert(!strcmp(p->choices[1],"Auto")&&p->choice_ints[1]==17);
 for(int i=1;i<=16;++i){char label[32];snprintf(label,sizeof label,"Adapter %d",i);assert(!strcmp(p->choices[i+1],label)&&p->choice_ints[i+1]==i);}
 p=row(MENU_RS232_BAUD);assert(p->num_choices==4);
 for(int i=0;i<4;++i){char label[16];snprintf(label,sizeof label,"%d",userport_bauds[i]);assert(p->choice_ints[i]==userport_bauds[i]&&!strcmp(p->choices[i],label));}
 p=row(MENU_RS232_PARITY);assert(p->num_choices==3);
 const char *parities[]={"None","Even","Odd"};
 for(int i=0;i<3;++i){assert(p->choice_ints[i]==i&&!strcmp(p->choices[i],parities[i]));}
 p=row(MENU_RS232_DATA_BITS);assert(p->num_choices==2&&p->choice_ints[0]==7&&p->choice_ints[1]==8);
 assert(!strcmp(p->choices[0],"7")&&!strcmp(p->choices[1],"8"));
 p=row(MENU_RS232_STOP_BITS);assert(p->num_choices==2&&p->choice_ints[0]==1&&p->choice_ints[1]==2);
 assert(!strcmp(p->choices[0],"1")&&!strcmp(p->choices[1],"2"));
 const int addresses[]={0,0xd700,0xde00,0xdf00,0xdf80};
 const char *address_labels[]={"Off","D700","DE00","DF00","DF80"};
 assert(network_modem_address_item->num_choices==5);
 for(int i=0;i<5;++i){assert(acia_network_addresses[i]==addresses[i]&&!strcmp(network_modem_address_item->choices[i],address_labels[i]));}
}
static void settings_and_persistence(void){
 for(int adapter=0;adapter<=17;++adapter)for(int rate=0;rate<4;++rate)
 for(int p=0;p<3;++p)for(int bits=7;bits<=8;++bits)for(int stops=1;stops<=2;++stops){
  selected=adapter;enabled=adapter!=0;baud=userport_bauds[rate];parity=p;data_bits=bits;stop_bits=stops;
  writes=0;modem_sets=0;build(VICE_MACHINE_C64);assert(!writes&&!modem_sets);layout();
  assert(row(MENU_RS232_FTDI)->value==(adapter==17?1:adapter==0?0:adapter+1));
  const int ids[]={MENU_RS232_BAUD,MENU_RS232_PARITY,MENU_RS232_DATA_BITS,MENU_RS232_STOP_BITS};
  const int vals[]={baud,p,bits,stops};
  for(int i=0;i<4;++i){struct menu_item *item=row(ids[i]);assert(item->choice_ints[item->value]==vals[i]);item->on_render(item);}
  assert(!writes);roundtrip();build(VICE_MACHINE_C64);
  assert(row(MENU_RS232_FTDI)->choice_ints[row(MENU_RS232_FTDI)->value]==adapter);
  for(int i=0;i<4;++i){struct menu_item *item=row(ids[i]);assert(item->choice_ints[item->value]==vals[i]);}
  choose(row(MENU_RS232_BAUD),userport_bauds[(rate+1)%4]);assert(baud==userport_bauds[(rate+1)%4]);
  choose(row(MENU_RS232_PARITY),(p+1)%3);assert(parity==(p+1)%3);
  choose(row(MENU_RS232_DATA_BITS),bits==7?8:7);assert(data_bits==(bits==7?8:7));
  choose(row(MENU_RS232_STOP_BITS),stops==1?2:1);assert(stop_bits==(stops==1?2:1));
  choose(row(MENU_RS232_FTDI),0);assert(!selected&&!enabled);
 }
 // Exercise every display choice as an action, not just initialization.
 for(int val=0;val<=17;++val){choose(row(MENU_RS232_FTDI),val);assert(selected==val&&enabled==(val!=0));}
}
static void rollback_and_live_status(void){
 selected=0;enabled=0;baud=2400;parity=0;data_bits=8;stop_bits=1;build(VICE_MACHINE_C64);
 struct menu_item *adapter=row(MENU_RS232_FTDI);int olderrors=errors;joy=1;int oldwrites=writes;
 choose(adapter,1);assert(!selected&&adapter->value==0&&errors==olderrors+1&&writes==oldwrites);
 joy=0;choose(adapter,17);assert(selected==17&&enabled&&adapter->value==1);
 joy=1;olderrors=errors;choose(adapter,1);assert(selected==17&&adapter->value==1&&errors==olderrors+1);joy=0;
 const int ids[]={MENU_RS232_FTDI,MENU_RS232_BAUD,MENU_RS232_PARITY,MENU_RS232_DATA_BITS,MENU_RS232_STOP_BITS};
 const char *names[]={"RsUserFTDI","RsUserBaud","RsUserParity","RsUserDataBits","RsUserStopBits"};
 const int requested[]={1,1200,2,7,2};
 for(int i=0;i<5;++i){int old=*value(names[i]);olderrors=errors;reject_resource=names[i];reject_once=1;
  choose(row(ids[i]),requested[i]);assert(!reject_once&&*value(names[i])==old&&errors==olderrors+1);
  assert(row(ids[i])->choice_ints[row(ids[i])->value]==old);
 }
 reject_resource="RsUserEnable";reject_once=1;olderrors=errors;
 choose(adapter,1);assert(selected==17&&enabled==1&&adapter->value==1&&errors==olderrors+1&&!reject_once);reject_resource=NULL;
 oldwrites=writes;adapter->value=-1;rs232_menu_changed(adapter);adapter->value=18;rs232_menu_changed(adapter);
 struct menu_item unknown={0};unknown.id=999;rs232_menu_changed(&unknown);
 assert(writes==oldwrites&&selected==17&&enabled);adapter->on_render(adapter);assert(adapter->value==1);
 struct menu_item *status=row(MENU_RS232_STATUS);oldwrites=writes;unsigned reads=snapshot_reads;
 const e64_rs232_usb_discovery_t snapshots[]={{0,0,0x8001,0},{17,0,0,0},{17,16,0x8000,0},{17,16,0x8000,1},{1,0,0x8000,0},{1,1,1,1},{17,0,0,0}};
 const char *labels[]={"Disabled","Not Detected","Detected","Detected","Not Detected","Detected","Not Detected"};
 for(unsigned i=0;i<sizeof snapshots/sizeof snapshots[0];++i){cached=snapshots[i];status->on_render(status);assert(!strcmp(status->displayed_value,labels[i])&&status->disabled);}
 assert(snapshot_reads==reads+7&&writes==oldwrites); // Hotplug consumer: no resource writes/USB calls.
 const int invalid[]={-1,18,100};
 for(unsigned i=0;i<sizeof invalid/sizeof invalid[0];++i){selected=invalid[i];oldwrites=writes;build(VICE_MACHINE_C64);
  adapter=row(MENU_RS232_FTDI);assert(adapter->value>=0&&adapter->value<adapter->num_choices&&selected==invalid[i]&&writes==oldwrites);}
 selected=0;baud=4800;build(VICE_MACHINE_C64);struct menu_item *speed=row(MENU_RS232_BAUD);
 assert(speed->num_choices==5&&speed->choice_ints[speed->value]==4800&&speed->choice_disabled[speed->value]);
 oldwrites=writes;speed->on_value_changed(speed);assert(writes==oldwrites&&baud==4800);
 choose(speed,2400);assert(baud==2400&&speed->num_choices==4);
}
static void modem_and_machines(void){
 selected=0;enabled=0;baud=2400;
 for(int index=0;index<5;++index){selected=enabled=0;modem_address=acia_network_addresses[index];writes=modem_sets=0;build(VICE_MACHINE_C64);
  assert(network_modem_address_item->value==index&&!writes&&!modem_sets);
  network_modem_address_item->value=(index+1)%5;network_modem_address_item->on_value_changed(network_modem_address_item);
  assert(modem_address==acia_network_addresses[(index+1)%5]&&modem_sets==1&&!selected&&!enabled);
  choose(row(MENU_RS232_FTDI),17);assert(modem_address==acia_network_addresses[(index+1)%5]);
  reject_modem=1;int old=modem_address,olderrors=errors;network_modem_address_item->value=index;modem_changed(network_modem_address_item);
  assert(modem_address==old&&network_modem_address_item->value==(index+1)%5&&errors==olderrors+1);reject_modem=0;

 }
 const int machines[]={BMC64_MACHINE_CLASS_C128,BMC64_MACHINE_CLASS_VIC20,BMC64_MACHINE_CLASS_PET,BMC64_MACHINE_CLASS_PLUS4,BMC64_MACHINE_CLASS_PLUS4EMU,99};
 for(unsigned i=0;i<sizeof machines/sizeof machines[0];++i){int machine=machines[i];writes=0;build(machine);assert(!writes);
  assert(!named(&system_menu,"USB Serial (RS-232)"));
  if(machine==BMC64_MACHINE_CLASS_C128){struct menu_item *rs=named(&system_menu,"RS-232 Devices");assert(rs&&rs->first_child==network_modem_address_item&&!rs->first_child->next);assert(!strcmp(rs->first_child->name,"RS-232 Modem Device"));}
  else {assert(!named(&system_menu,"RS-232 Devices"));}
  if(machine==BMC64_MACHINE_CLASS_VIC20){assert(!network_modem_address_item&&network_modem_baud_item);
   assert(network_menu.first_child->type==DIVIDER&&network_menu.first_child->next==network_modem_baud_item);
   assert(network_modem_baud_item->num_choices==3);
   const int rates[]={300,1200,2400};for(int j=0;j<3;++j){assert(network_modem_baud_item->choice_ints[j]==rates[j]);network_modem_baud_item->value=j;modem_changed(network_modem_baud_item);assert(modem_baud==rates[j]);}
  } else {assert(!network_modem_baud_item);}
  if(machine==BMC64_MACHINE_CLASS_PET||machine==BMC64_MACHINE_CLASS_PLUS4||machine==BMC64_MACHINE_CLASS_PLUS4EMU)assert(!network_modem_address_item);
  struct menu_item empty={0};count=0;emux_add_rs232_options(&empty);assert(!count&&!empty.first_child);
 }
}
static void save_and_restart(void){
 const char *old="network_device=2\nwebui_enabled=1\nwebui_pin=1234\nnetwork_modem_base=0\nnetwork_modem_baud=2400\n";
 assert(sd_mkdir("/system")==SD_OK);
 assert(sd_write_file(NETWORK_PREFS_FILE,old,strlen(old))==SD_OK);
 selected=17;enabled=1;baud=2400;parity=0;data_bits=8;stop_bits=1;joy=0;
 build(VICE_MACHINE_C64);writes=0;load_global_network_prefs();
 assert(!writes && selected==17 && enabled && baud==2400 && !parity && data_bits==8 && stop_bits==1);
 network_modem_address_item->value=1;
 modem_changed(network_modem_address_item);
 assert(modem_address==0xd700 && selected==17 && enabled);
 choose(row(MENU_RS232_BAUD),9600);choose(row(MENU_RS232_PARITY),2);
 choose(row(MENU_RS232_DATA_BITS),7);choose(row(MENU_RS232_STOP_BITS),2);
 struct menu_item *save=usb()->next;
 menu_cursor_item[0]=save;do_on_value_changed(save);assert(reboots==1);
 NetworkPrefs prefs;
 assert(!network_prefs_load(&prefs,NULL));
 assert(prefs.device==2 && prefs.webui_enabled==1 && !strcmp(prefs.webui_pin,"1234"));
 assert(prefs.modem_base==0xd700 && prefs.modem_baud==2400);
 assert(prefs.ftdi.adapter==17 && prefs.ftdi.enabled && prefs.ftdi.baud==9600);
 assert(prefs.ftdi.parity==2 && prefs.ftdi.data_bits==7 && prefs.ftdi.stop_bits==2);
 assert(!save_global_network_prefs());
 // Simulate new resources and a newly built menu after restart.
 selected=1;enabled=0;baud=300;parity=0;data_bits=8;stop_bits=1;modem_address=0;
 build(VICE_MACHINE_C64);load_global_network_prefs();
 assert(network_modem_address_item->value==1 && modem_address==0xd700);
 assert(selected==17 && enabled && baud==9600 && parity==2 && data_bits==7 && stop_bits==2);
 check_heading("9600,O,7,2");
 assert(sd_mkdir(NETWORK_PREFS_FILE ".new")==SD_OK);
 save=usb()->next;menu_cursor_item[0]=save;
 choose(row(MENU_RS232_FTDI),0);
 int old_errors=errors;do_on_value_changed(save);
 assert(errors==old_errors+1 && reboots==1);
 assert(!network_prefs_load(&prefs,NULL) && prefs.ftdi.adapter==17);
 assert(!rmdir("system/network-prefs.txt.new"));
 do_on_value_changed(save);assert(reboots==2);
 assert(!network_prefs_load(&prefs,NULL) && !prefs.ftdi.adapter && !prefs.ftdi.enabled);
 selected=17;enabled=1;load_global_network_prefs();
 assert(!selected && !enabled && modem_address==0xd700);
 check_heading("Off");
 const char *malformed="network_device=2\nwebui_enabled=1\nftdi=17,9600,0,8,1,4294967297\n";
 assert(sd_write_file(NETWORK_PREFS_FILE,malformed,strlen(malformed))==SD_OK);
 assert(!network_prefs_load(&prefs,NULL) && prefs.device==2 && prefs.webui_enabled && !prefs.ftdi.baud);
}
int main(void){
 assert(!setenv("SD_TEST_ROOT",".",1));
 settings_and_persistence();heading_updates();rollback_and_live_status();modem_and_machines();save_and_restart();
 puts("PASS FTDI heading: right alignment, collapsed and expanded markers, live framing and adapter updates, and restored settings");
 puts("PASS RS-232 menu: labels, order, button dispatch, save/reboot, restart and independent FTDI/virtual modem settings");
}
'''

with tempfile.TemporaryDirectory(prefix='e64-rs232-menu-', dir=r / 'build') as tmp:
    p = Path(tmp) / 'test.c'
    p.write_text(code)
    exe = Path(tmp) / 'test'
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                    '-I' + str(v), '-I' + str(r / 'src'), '-I' + str(r / 'src/sdcard'),
                    p, r / 'src/network_prefs.c', r / 'src/sdcard/sd_fs_file.c',
                    r / 'tools/sdcard/sd_fs_posix.c', '-o', exe], check=True)
    subprocess.run([exe], check=True, cwd=tmp)
print('PASS: current production menu structure and extracted callbacks; historical baseline comparison unavailable')
