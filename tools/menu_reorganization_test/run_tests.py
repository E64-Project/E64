#!/usr/bin/env python3
"""Execute production menu construction fragments and node reparenting.
No emulator resources or SD data are written. Dumps before/after hierarchies.
"""
from pathlib import Path
import re,tempfile,subprocess,tarfile,argparse,json
from collections import Counter
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline-archive',type=Path,help='Optional read-only pre-edit source archive for before.txt');args=parser.parse_args()
r=Path(__file__).resolve().parents[2];menu=(r/'third_party/common/menu.c').read_text();cart=(r/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text();vice=(r/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text();cfg=(r/'third_party/common/menu_configs.c').read_text()
def fn(s,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]
helpers='\n'.join(fn(menu,n) for n in ['move_menu_item','menu_move_ieee488','menu_child_named','menu_child_id','menu_move_id','menu_global_drive_priority','menu_reorganize_storage','menu_reorganize_cartridge','menu_reorganize_video','menu_system_priority','menu_reorder_system'])
drive=menu[menu.index('  drive_parent = ui_menu_add_folder(root, "Drives");'):menu.index('  parent = emux_add_cartridge_options(root);')]
video=menu[menu.index('  int defaultHStretch;',menu.index('void build_menu(')):menu.index('  if (emux_machine_class == BMC64_MACHINE_CLASS_C128)',menu.index('  int defaultHStretch;',menu.index('void build_menu(')))]
a=menu.index('    child = network_modem_address_item = ui_menu_add_multiple_choice(',menu.index('void build_menu('));b=menu.index('\n  }',a);modem=menu[a:b]
ui=(r/'third_party/common/ui.c').read_text()
nav='\n'.join(fn(ui,n) for n in ['ui_item_at_index','ui_cursor_is_selectable','ui_is_network_address_field','ui_row_pitch','ui_refresh_menu_window','ui_select_first_interactive_item','ui_move_cursor','ui_root_add_boundary_color','ui_root_add_boundary','ui_root_skip_rows','ui_root_collect_groups','ui_root_collect_boundaries','ui_root_boundary_pixels','ui_root_visible_bottom','ui_traverse_children','ui_traverse','ui_collapse_folders','ui_return_to_root','ui_menu_item_label'])
production=helpers+'\n'+fn(vice,'emux_add_drive_option')+'\n'+'\n'.join(fn(cart,n) for n in ['emux_refresh_cartridge_menu','update_reu_image_enabled','update_ide64_geometry_enabled','update_ide64_usb_enabled','emux_add_cartridge_options'])+'\n'+'\n'.join(fn(cfg,n) for n in ['base_name','update_autostart_label','add_item','build_configs_autostart_items','build_configs_drive_items','update_name_labels','protection_label','menu_configs_label_save_item','config_rom_row_render','config_rom_summary_render','config_rom_summary_changed','add_config_rom_summary','build_configs_menu'])
production='#define CONFIG_ROM_VALUE_COLS 25\nvoid menu_configs_label_save_item(menu_item*);\n'+production
production+='\n'+nav+'\n'+fn(cart,'emux_add_machine_options')+'\n'+fn((r/'third_party/common/menu_power.c').read_text(),'build_power_menu')
all_source=production+drive+video+modem
ids=sorted(set(re.findall(r'\b(?:MENU_[A-Z0-9_]+|BMC64_MACHINE_CLASS_[A-Z0-9_]+|DRIVE_PC_[A-Z0-9_]+|Setting_[A-Za-z0-9_]+)\b',all_source))|{'MENU_C64_ATTACH_CART_8K','MENU_C64_ATTACH_CART_16K','MENU_CALC_TIMING','MENU_SCALING_INTERPOLATION','MENU_USE_SCALING_PARAMS_0','MENU_SHADER_ENABLE','MENU_NETWORK_MODEM_ADDRESS','MENU_LOGGING_DESTINATION'})
ids=[x for x in ids if x!='MENU_ID_DO_NOTHING']
assert 'build_configs_autostart_items(machine_parent);' in menu
assert 'menu_reorganize_storage(root,drive_parent,advanced_drive_parent,machine_parent,network_folder);' in menu
assert 'menu_reorganize_video(video_parent);' in menu
assert 'menu_reorganize_cartridge(root);' in menu
for name in ['Drive Reference >','Drive ROM Reference >','IEEE-488 Help >']:
 # Definitions remain archived in source, but are not constructed in build_menu.
 assert name not in menu[menu.index('void build_menu('):menu.index('void menu_autostart(')]
assert 'ui_menu_add_folder(machine_parent, "Autostart")' not in menu and 'ui_menu_add_folder(machine_parent, "Warp")' not in menu
assert 'ui_menu_add_toggle(MENU_WARP_MODE, root,' in menu
for unit in range(8,12):assert f'MENU_DETACH_DISK_{unit}, parent, "Remove Disk"' in menu
assert 'Load & Run (Disk 8)' not in menu and 'Load & Run Disk >' in menu
code=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <cstdlib>
#include <string>
#include <vector>
#include <deque>
#include <map>
#include <set>
#include <fstream>
#include "ui.h"
#include "menu_theme.h"
enum { @IDS@ };
#define HAVE_NETWORK 1
#define VIC_INDEX 0
@DEFAULTS@
static int emux_machine_class=BMC64_MACHINE_CLASS_C64;
static unsigned long circle_get_ticks(){return 0;}
static void emux_get_string_1(int setting,const char **out,int index){assert(setting==Setting_ConfigROM&&index>=0&&index<3);*out="Default";}
static menu_item menu_roots[NUM_MENU_ROOTS],*menu_cursor_item[NUM_MENU_ROOTS];
static int current_menu,menu_cursor[NUM_MENU_ROOTS],menu_window_top[NUM_MENU_ROOTS],menu_window_bottom[NUM_MENU_ROOTS],max_index[NUM_MENU_ROOTS];
#define MAX_ROOT_SECTION_BOUNDARIES 128
static int root_section_boundary_count,root_section_boundaries[MAX_ROOT_SECTION_BOUNDARIES],root_section_colors[MAX_ROOT_SECTION_BOUNDARIES];
volatile int ui_enabled=1;static int ui_external_owner,ui_key_action,ui_transparent,ui_transparent_layer,ui_render_current_item_only,renders;
#define ACTION_None 0
static void (*raw_keycode_func)(long);
static void ui_text_cursor_reset(){}
static void cursor_pos_updated(){}
static void ui_traverse(void);
menu_item *ui_pop_menu(){assert(false);return nullptr;}
void ui_render_single_frame(){ui_traverse();renders++;}
static int resource_reads,callback_calls,seed_enabled;
#define CARTRIDGE_EASYFLASH 32
static int attached_cartridge_type=-1;
static int cartridge_type_enabled(int type){assert(type==CARTRIDGE_EASYFLASH);return attached_cartridge_type==type;}static std::string startup;
static std::deque<menu_item> nodes;
static menu_item *status_item,*save_item,*protection_item,*cleanup_parent,*cleanup_item;
static int legacy_count,protection_state;
struct RunningConfig {const char *id,*name;};
static RunningConfig running_config={"custom","Current Test"};
static RunningConfig *configs_running(){return &running_config;}
static int configs_protection_status(const char *id){assert(!strcmp(id,"custom"));return protection_state;}
static int configs_deleted_count(){return legacy_count;}

static menu_item *easyflash_save_item,*reu_size_item,*reu_image_menu,*reu_attach_image_item,*reu_detach_image_item,*reu_save_image_item,*reu_save_image_as_item,*ide64_usb_address_item,*autostart_folder,*network_modem_address_item;
static menu_item *ide64_autodetect_items[4],*ide64_cylinders_items[4],*ide64_heads_items[4],*ide64_sectors_items[4];
static menu_item *h_center_item[2],*v_center_item[2],*h_border_item[2],*v_border_item[2],*h_stretch_item[2],*v_stretch_item[2];
static int reu_size_to_index[8]={128,256,512,1024,2048,4096,8192,16384};
static const int acia_network_addresses[5]={0,0xd700,0xde00,0xdf00,0xdf80};
static const char*acia_network_address_labels[5]={"Off","D700","DE00","DF00","DF80"};
static int acia_address;
static int circle_get_acia_network_address(){return acia_address;}
static int acia_network_address_index(int address){for(int n=0;n<5;n++)if(acia_network_addresses[n]==address)return n;return 0;}
static int drive_get_button(int unit){return unit==0?1:unit==1?6:0;}
static int resources_get_int(const char *name,int *value){resource_reads++;*value=!strcmp(name,"REUsize")?512:!strcmp(name,"IDE64version")?2:(!strcmp(name,"REU")||!strcmp(name,"IEEE488"))?seed_enabled:1;return 0;}
static int resources_get_int_sprintf(const char *format,int *value,int unit){resource_reads++;char name[128];snprintf(name,sizeof(name),format,unit);*value=strstr(name,"ParallelCable")?DRIVE_PC_STANDARD:strstr(name,"Cylinders")?100+unit:strstr(name,"Heads")?4:strstr(name,"Sectors")?32:unit%2;return 0;}
static int resources_get_string(const char*name,const char **out){resource_reads++;*out=!strcmp(name,"IDE64USBServerAddress")?"127.0.0.1:6423":"/carts/existing-image.bin";return 0;}
static int emux_get_int_1(int,int *value,int unit){*value=unit%2;return 0;}
static void menu_value_changed(menu_item *item){assert(item);callback_calls++;}
static void configs_item_chosen(menu_item *item){assert(item);callback_calls++;}
static void reboot_selected(menu_item*item){menu_value_changed(item);}
static void power_off_selected(menu_item*item){menu_value_changed(item);}
static const char *configs_autostart(){return startup.c_str();}
static struct {int max_border_w,max_border_h,max_stretch_h;} canvas_state[1]={{32,20,1800}};
static menu_item *add(menu_item *parent,int id,const char *name,int type){nodes.emplace_back();auto*n=&nodes.back();memset(n,0,sizeof(*n));n->id=id;n->type=(menu_item_type)type;n->menu_left=16;n->menu_top=24;n->menu_width=320;n->menu_height=200;snprintf(n->name,sizeof(n->name),"%s",name);if(parent){auto**p=&parent->first_child;while(*p)p=&(*p)->next;*p=n;}return n;}
menu_item *ui_menu_add_folder(menu_item *p,char *name){return add(p,-1,name,FOLDER);}
menu_item *ui_menu_add_button(int id,menu_item*p,const char *name){return add(p,id,name,BUTTON);}
menu_item *ui_menu_add_toggle(int id,menu_item*p,char*name,int value){auto*n=add(p,id,name,TOGGLE);n->value=value;return n;}
menu_item *ui_menu_add_multiple_choice(int id,menu_item*p,const char *name){return add(p,id,name,MULTIPLE_CHOICE);}
menu_item *ui_menu_add_range(int id,menu_item*p,char*name,int low,int high,int step,int value){auto*n=add(p,id,name,RANGE);n->min=low;n->max=high;n->step=step;n->value=value;return n;}
menu_item *ui_menu_add_divider(menu_item*p){return add(p,-1,"",DIVIDER);}
menu_item *ui_menu_add_read_only_heading(menu_item*p,const char*text){auto*n=add(p,-1,text,READ_ONLY_HEADING);n->disabled=1;return n;}
menu_item *ui_menu_add_text_field_limit(int id,menu_item*p,char*name,char*value,int limit){auto*n=add(p,id,name,TEXTFIELD);snprintf(n->str_value,sizeof(n->str_value),"%s",value);n->max_length=limit;return n;}
@PRODUCTION@
static menu_item *seed_drives(menu_item *root,menu_item **out){menu_item *drive_parent,*parent,*advanced_drive_parent=nullptr;int tmp;
@DRIVE@
*out=advanced_drive_parent;return drive_parent;}
static void seed_video(menu_item *parent){menu_item *child;
@VIDEO@
}
static void seed_modem(menu_item *rs232_folder){menu_item *child;
@MODEM@
}
static void collect(menu_item *n,std::set<menu_item*> &seen,std::map<menu_item*,menu_item>&snapshot){for(;n;n=n->next){assert(seen.insert(n).second);snapshot[n]=*n;collect(n->first_child,seen,snapshot);}}
static void dump(std::ostream &out,menu_item *n,int level=0){for(;n;n=n->next){out<<std::string(level*2,' ')<<ui_menu_item_label(n)<<" ["<<n->id<<","<<n->value<<","<<n->sub_id<<"]\n";dump(out,n->first_child,level+1);}}
static int count(menu_item*n,int id){int result=0;for(;n;n=n->next){result+=n->id==id;result+=count(n->first_child,id);}return result;}
int main(int argc,char**argv){assert(argc==2);
 for(int state=0;state<5;state++){
  nodes.clear();resource_reads=callback_calls=0;seed_enabled=state%2;attached_cartridge_type=state==2?CARTRIDGE_EASYFLASH:state%2?1:-1;acia_address=acia_network_addresses[state];startup.clear();
  auto*root=add(nullptr,-1,"root",FOLDER);
  legacy_count=state==4;protection_state=state%2;status_item=ui_menu_add_folder(root,(char*)"Config");build_configs_menu(status_item);
  const int config_ids[]={MENU_CONFIGS_SELECT,MENU_CONFIGS_NEW,MENU_SAVE_SETTINGS,MENU_CONFIGS_RENAME,MENU_CONFIGS_PROTECTION,MENU_CONFIGS_DELETE};
  const char *config_names[]={"Select An Existing Config >","Create Config From Current Settings","Save Changes To The Current Config","Rename A Config >",state%2?"Protect The Current Config: On":"Protect The Current Config: Off","Delete An Existing Config >"};
  auto*action=status_item->first_child;for(int n=0;n<6;n++){assert(action&&action->id==config_ids[n]&&!strcmp(action->name,config_names[n]));assert(action->type==BUTTON&&!action->first_child);assert(action->on_value_changed==(n==2?nullptr:configs_item_chosen));assert(8+16+strlen(action->name)*8<=320-8);action=action->next;if(n==0){assert(action&&action->type==FOLDER&&!action->is_expanded&&!strcmp(action->name,"ROMs in this Config >"));auto*row=action->first_child;for(int i=0;i<3;i++){assert(row&&row->disabled&&row->type==READ_ONLY_DESCRIPTION&&row->on_render);row=row->next;}assert(!row);action=action->next;}}
  if(legacy_count){assert(action&&action->id==MENU_CONFIGS_RESTORE&&!action->next);}else assert(!action);
  assert(!strcmp(status_item->name,"Active Config: Current Test"));assert(save_item->id==MENU_SAVE_SETTINGS&&cleanup_parent==status_item);
  auto*system=ui_menu_add_folder(root,(char*)"System");auto*network=ui_menu_add_folder(system,(char*)"Network");auto*rs232=ui_menu_add_folder(system,(char*)"Modem & RS-232 Devices");seed_modem(rs232);auto*modem=network_modem_address_item;modem->on_value_changed=menu_value_changed;
  auto*fan=ui_menu_add_folder(system,(char*)"Cooling Fan");
  auto*logging=ui_menu_add_button(MENU_LOGGING_DESTINATION,system,"Logging");
  ui_menu_add_folder(system,(char*)"GPIO");
  ui_menu_add_folder(system,(char*)"Prefs");
  emux_add_machine_options(system);auto*roms=menu_child_named(system,"ROMs");build_power_menu(system);auto*power=menu_child_named(system,"Power");
  build_configs_autostart_items(system);auto*boot_warp=ui_menu_add_toggle(MENU_AUTOSTART_WARP,system,(char*)"Autostart Warp",state%2);boot_warp->on_value_changed=menu_value_changed;
  menu_item *global;auto*drives=seed_drives(root,&global);build_configs_drive_items(drives);emux_add_cartridge_options(root);auto*cartridge=menu_child_named(root,"Cartridge");auto*reu_folder=menu_child_named(cartridge,"RAM Expansion");auto*ide=menu_child_named(cartridge,"IDE64");auto*reu=menu_child_id(reu_folder,MENU_REU);assert(reu&&ide);
  auto*video=ui_menu_add_folder(root,(char*)"Video");ui_menu_add_button(MENU_CALC_TIMING,video,"Video Mode >");ui_menu_add_toggle(MENU_SCALING_INTERPOLATION,video,(char*)"Scaling Interpolation",1);ui_menu_add_toggle(MENU_USE_SCALING_PARAMS_0,video,(char*)"Apply Scaling Parameters At Boot",1);auto*shader=ui_menu_add_folder(video,(char*)"CRT Shader");ui_menu_add_toggle(MENU_SHADER_ENABLE,shader,(char*)"Enable CRT Shader?",1);auto*color=ui_menu_add_folder(video,(char*)"Color Adjustments");ui_menu_add_button(9004,color,"Reset");seed_video(video);
  std::set<menu_item*> seen;std::map<menu_item*,menu_item> before;collect(root,seen,before);if(state==0){std::ofstream out(std::string(argv[1])+"/constructed-before-reparent.txt");dump(out,root);}
  std::set<menu_item*> renamed={reu_folder,reu,menu_child_id(drives,MENU_DRIVE_CHANGE_ROM),menu_child_id(cartridge,MENU_DETACH_CART)};
  for(int unit=8;unit<=11;unit++){char name[16];snprintf(name,sizeof(name),"Drive %d",unit);renamed.insert(menu_child_named(global,name));}
  int reads=resource_reads;menu_move_ieee488(root,drives,drives);menu_reorganize_storage(root,drives,global,system,network);menu_reorganize_video(video);menu_reorganize_cartridge(root);menu_reorder_system(system);assert(resource_reads==reads&&callback_calls==0);
  const char *system_order[]={"Autostart","ROMs","Memory Expansion","Prefs","Modem & RS-232 Devices","Power","Network","GPIO","Cooling Fan","Logging"};
  auto*section=system->first_child;
  for(const char *name:system_order){assert(section&&!strcmp(section->name,name));section=section->next;}
  assert(!section&&fan->next==logging&&!logging->next&&rs232->next==power);
  std::set<menu_item*> after;std::map<menu_item*,menu_item> snapshot;collect(root,after,snapshot);assert(after.size()==seen.size()+2);for(auto*n:seen)assert(after.count(n));
  for(auto &pair:before){auto*ptr=pair.first;auto old=pair.second;old.next=ptr->next;old.first_child=ptr->first_child;if(strcmp(old.name,ptr->name))assert(renamed.count(ptr));memcpy(old.name,ptr->name,sizeof(old.name));assert(!memcmp(&old,ptr,sizeof(old)));}
  const int models[]={MENU_DRIVE_CHANGE_MODEL_8,MENU_DRIVE_CHANGE_MODEL_9,MENU_DRIVE_CHANGE_MODEL_10,MENU_DRIVE_CHANGE_MODEL_11};
  for(int unit=8;unit<=11;unit++){
   char name[16];snprintf(name,sizeof(name),"Drive %d",unit);auto*drive=menu_child_named(drives,name);assert(drive);auto*advanced=menu_child_named(drive,"Advanced Settings");assert(advanced&&menu_child_id(drive,models[unit-8])&&!menu_child_id(advanced,models[unit-8])&&count(root,models[unit-8])==1);assert(!menu_child_named(global,name));assert(!strcmp(drive->first_child->name,"Attach Disk >")&&!strcmp(drive->first_child->next->name,"Remove Disk"));assert(drive->first_child->next->next->id==models[unit-8]&&!strcmp(drive->first_child->next->next->name,"Change Model >")&&drive->first_child->next->next->next==advanced&&advanced->next==nullptr);const int attach_ids[]={MENU_ATTACH_DISK_8,MENU_ATTACH_DISK_9,MENU_ATTACH_DISK_10,MENU_ATTACH_DISK_11};const int remove_ids[]={MENU_DETACH_DISK_8,MENU_DETACH_DISK_9,MENU_DETACH_DISK_10,MENU_DETACH_DISK_11};assert(drive->first_child->id==attach_ids[unit-8]&&drive->first_child->next->id==remove_ids[unit-8]);assert(count(root,attach_ids[unit-8])==1&&count(root,remove_ids[unit-8])==1);assert(count(drive->first_child,MENU_DRIVE_CHANGE_ROM)==0);
   auto*true_drive=menu_child_id(advanced,MENU_DRIVE_TRUE_EMULATION);assert(true_drive&&true_drive->sub_id==unit&&true_drive->value==unit%2);for(auto*n=advanced->first_child;n;n=n->next)if(n->id==MENU_DRIVE_RAM_2000||n->id==MENU_DRIVE_RAM_4000||n->id==MENU_DRIVE_RAM_6000||n->id==MENU_DRIVE_RAM_8000||n->id==MENU_DRIVE_RAM_A000)assert(n->sub_id==unit);
  }
  assert(!strcmp(menu_child_id(drives,MENU_CREATE_EMPTY_DISK_MENU)->name,"Create Empty Disk >"));assert(count(drives->first_child,MENU_CREATE_EMPTY_DISK_MENU)==1&&menu_child_id(drives,MENU_CREATE_EMPTY_DISK_MENU)&&!menu_child_id(global,MENU_CREATE_EMPTY_DISK_MENU));assert(menu_child_named(drives,"Drive 11")->next->id==MENU_CREATE_EMPTY_DISK_MENU&&menu_child_named(drives,"Drive 11")->next->next->id==MENU_IEEE488&&menu_child_named(drives,"Drive 11")->next->next->next==global);assert(global->first_child->id==MENU_DRIVE_CHANGE_ROM&&!strcmp(global->first_child->name,"Drive ROMs >"));assert(global->first_child->next==ide&&menu_child_id(drives,MENU_IEEE488)&&!menu_child_id(global,MENU_IEEE488));assert(count(root,MENU_IEEE488_HELP)==0&&count(root,MENU_DRIVE_REFERENCE)==0&&count(root,MENU_DRIVE_ROM_REFERENCE)==0);assert(count(root,MENU_IEEE488)==1&&count(cartridge->first_child,MENU_IEEE488)==0);assert(!menu_child_named(cartridge,"IDE64")&&!menu_child_named(cartridge,"RAM Expansion"));assert(menu_child_named(system,"Memory Expansion")==reu_folder&&!strcmp(reu->name,"REU"));assert(reu_size_item->value==2&&reu_image_menu->first_child==reu_attach_image_item&&reu_image_menu->disabled==!seed_enabled);
  assert(reu_image_menu->type==FOLDER&&!strcmp(reu_image_menu->name,"REU File"));
  assert(menu_child_named(reu_folder,"REU File")==reu_image_menu);
  menu_item *reu_controls[]={reu_attach_image_item,reu_detach_image_item,reu_save_image_item,reu_save_image_as_item};
  const int reu_ids[]={MENU_REU_ATTACH_IMAGE,MENU_REU_DETACH_IMAGE,MENU_REU_SAVE_IMAGE,MENU_REU_SAVE_IMAGE_AS};
  const char *reu_labels[]={"Load File >","Clear Image","Save Now","Save As >"};
  auto*reu_control=reu_image_menu->first_child;
  for(int n=0;n<4;n++){assert(reu_control==reu_controls[n]&&reu_control->type==BUTTON&&reu_control->id==reu_ids[n]);assert(!strcmp(ui_menu_item_label(reu_control),reu_labels[n]));assert(reu_control->disabled==!seed_enabled);reu_control=reu_control->next;}
  assert(!reu_control&&reu->value==seed_enabled&&reu->on_value_changed==menu_value_changed);

  for(int device=0;device<4;device++){char name[20];snprintf(name,sizeof(name),"ATA Device %d",device+1);auto*ata=menu_child_named(ide,name);assert(ata&&menu_child_id(ata,MENU_IDE64_IMAGE_1+device));assert(!strcmp(menu_child_id(ata,MENU_IDE64_IMAGE_1+device)->name,"Attach Disk >"));int attachments=0;for(auto*n=ata->first_child;n;n=n->next)if(!strcmp(n->name,"Attach Disk >"))attachments++;assert(attachments==1);assert(ide64_cylinders_items[device]->value==101+device&&ide64_cylinders_items[device]->step==1);assert(ide64_heads_items[device]->max==16&&ide64_sectors_items[device]->max==63);}
  for(int id:{MENU_C64_ATTACH_CART,MENU_DETACH_CART,MENU_SAVE_EASYFLASH,MENU_CART_FREEZE})assert(menu_child_id(cartridge,id));
  assert(!menu_child_named(root,"ROM Images"));assert(menu_child_id(cartridge,MENU_LOAD_ROM_IMAGE)&&count(root,MENU_LOAD_ROM_IMAGE)==1);assert(count(root,MENU_DETACH_CART)==1);for(int id:{MENU_C64_ATTACH_CART_8K,MENU_C64_ATTACH_CART_16K,MENU_C64_ATTACH_CART_ULTIMAX})assert(count(root,id)==0);

  assert(menu_child_id(rs232,MENU_NETWORK_MODEM_ADDRESS)==modem&&!menu_child_id(network,MENU_NETWORK_MODEM_ADDRESS));assert(modem->num_choices==5&&modem->value==state&&modem->on_value_changed==menu_value_changed);for(int n=0;n<5;n++)assert(!strcmp(modem->choices[n],acia_network_address_labels[n]));modem->on_value_changed(modem);assert(callback_calls==1);
  auto*group=system->first_child;assert(!strcmp(group->name,"Autostart")&&group->type==FOLDER&&group->next==roms);auto*item=group->first_child;assert(!strcmp(item->name,"Current Autostart")&&item->disabled&&item->type==BUTTON&&item->id==MENU_ID_DO_NOTHING&&item->prefer_str&&!item->on_value_changed&&!strcmp(item->displayed_value,"None"));item=item->next;assert(item->id==MENU_CONFIGS_AUTOSTART_FILE&&!strcmp(item->name,"Autostart PRG/Disk >"));item=item->next;assert(item->id==MENU_CONFIGS_CLEAR_AUTOSTART&&!strcmp(item->name,"Clear Autostart PRG/Disk"));assert(item->next==boot_warp&&boot_warp->next==nullptr&&roms->next==reu_folder);assert(!menu_child_named(system,"Warp"));startup="/disks/Boot Disk.d64";update_autostart_label();assert(!strcmp(autostart_folder->name,"Current Autostart")&&!strcmp(autostart_folder->displayed_value,"Boot Disk.d64"));startup="/programs/demo.prg";update_autostart_label();assert(!strcmp(autostart_folder->displayed_value,"demo.prg"));startup.clear();update_autostart_label();assert(!strcmp(autostart_folder->displayed_value,"None"));assert(autostart_folder->disabled&&!autostart_folder->on_value_changed);assert(menu_child_id(group,MENU_CONFIGS_AUTOSTART_FILE)->on_value_changed==configs_item_chosen);assert(menu_child_id(group,MENU_CONFIGS_CLEAR_AUTOSTART)->on_value_changed==configs_item_chosen);assert(boot_warp->on_value_changed==menu_value_changed&&boot_warp->value==state%2);
  auto*screen=menu_child_named(video,"Screen Adjustments");assert(screen);
  const int adjustments[]={MENU_SCALING_INTERPOLATION,MENU_USE_SCALING_PARAMS_0,MENU_H_CENTER_0,MENU_V_CENTER_0,MENU_H_BORDER_0,MENU_V_BORDER_0,MENU_H_STRETCH_0,MENU_V_STRETCH_0,MENU_INTEGER_SCALE_W_0,MENU_INTEGER_SCALE_H_0};
  auto*adjustment=screen->first_child;for(int id:adjustments){assert(adjustment&&adjustment->id==id);adjustment=adjustment->next;}assert(!adjustment);
  auto*v=video->first_child;assert(v->id==MENU_CALC_TIMING&&v->next==screen&&screen->next==color&&color->next==shader&&!shader->next);
  auto*freeze_action=menu_child_id(cartridge,MENU_CART_FREEZE);auto*easyflash_action=menu_child_id(cartridge,MENU_SAVE_EASYFLASH);
  assert(freeze_action&&easyflash_action&&!freeze_action->disabled&&easyflash_action->disabled==!cartridge_type_enabled(CARTRIDGE_EASYFLASH));
  assert(!strcmp(ui_menu_item_label(freeze_action),"Press Cartridge Freeze Button"));
  assert(!strcmp(ui_menu_item_label(easyflash_action),"Save EasyFlash Changes"));
  int original_type=attached_cartridge_type;for(int type:{-1,1,CARTRIDGE_EASYFLASH,-1,CARTRIDGE_EASYFLASH,1}){attached_cartridge_type=type;emux_refresh_cartridge_menu();assert(easyflash_action==easyflash_save_item&&easyflash_action->disabled==(type!=CARTRIDGE_EASYFLASH));assert(!freeze_action->disabled&&reu_size_item->value==2);}attached_cartridge_type=original_type;emux_refresh_cartridge_menu();
  const int cart_order[]={MENU_C64_ATTACH_CART,MENU_LOAD_ROM_IMAGE,MENU_DETACH_CART,-1,MENU_MAKE_CART_DEFAULT,MENU_SAVE_EASYFLASH,MENU_CART_FREEZE};

  auto*c=cartridge->first_child;for(int id:cart_order){assert(c);if(id<0)assert(c->type==DIVIDER);else assert(c->id==id);c=c->next;}assert(!c);assert(!strcmp(menu_child_id(cartridge,MENU_DETACH_CART)->name,"Remove Cartridge"));assert(!strcmp(menu_child_id(cartridge,MENU_C64_ATTACH_CART)->name,"Load Cartridge >"));assert(!strcmp(menu_child_id(cartridge,MENU_MAKE_CART_DEFAULT)->name,"Set Attached Cartridge as Default"));

  std::string first;{std::ostringstream out;dump(out,root);first=out.str();}menu_reorganize_storage(root,drives,global,system,network);menu_reorganize_video(video);menu_reorganize_cartridge(root);menu_reorder_system(system);{std::ostringstream out;dump(out,root);assert(out.str()==first);}after.clear();snapshot.clear();collect(root,after,snapshot);assert(after.size()==seen.size()+2);
  if(state==0){std::ofstream out(std::string(argv[1])+"/after.txt");dump(out,root);}
  protection_state=-1;protection_label();assert(!strcmp(protection_item->name,"Protect Current Config: Unavailable"));
  protection_state=0;protection_label();assert(!strcmp(protection_item->name,"Protect The Current Config: Off"));
  protection_state=1;protection_label();assert(!strcmp(protection_item->name,"Protect The Current Config: On"));
  running_config.name="Other Config";update_name_labels();assert(!strcmp(status_item->name,"Active Config: Other Config"));running_config.name="Current Test";update_name_labels();
  // Every visible submenu-group boundary uses gray, for +, -, and mixed trees.
  for(int expanded=0;expanded<3;expanded++){
   for(auto*n:after)if(n!=root&&n->type==FOLDER)n->is_expanded=0;
   drives->is_expanded=global->is_expanded=ide->is_expanded=1;
   for(int unit=8;unit<=11;unit++){char name[16];snprintf(name,sizeof(name),"Drive %d",unit);menu_child_named(drives,name)->is_expanded=expanded==1||(expanded==2&&unit%2);}
   for(int device=1;device<=4;device++){char name[20];snprintf(name,sizeof(name),"ATA Device %d",device);menu_child_named(ide,name)->is_expanded=expanded==1||(expanded==2&&device%2);}
   menu_roots[0]=*root;current_menu=0;menu_cursor[0]=0;menu_window_top[0]=0;ui_traverse();
   assert(root_section_boundary_count<MAX_ROOT_SECTION_BOUNDARIES);
   for(int unit=8;unit<=11;unit++){char name[16];snprintf(name,sizeof(name),"Drive %d",unit);auto*drive=menu_child_named(drives,name);int row=drive->render_index,matches=0;for(int i=0;i<root_section_boundary_count;i++)if(root_section_boundaries[i]==row){assert(root_section_colors[i]==E64_MENU_DEVICE_SEPARATOR);matches++;}int adjacent=unit>8&&(expanded==1||(expanded==2&&(unit-1)%2));assert(matches==(drive->is_expanded||adjacent?1:0));auto*advanced=menu_child_named(drive,"Advanced Settings");if(drive->is_expanded)for(int i=0;i<root_section_boundary_count;i++)assert(root_section_boundaries[i]!=advanced->render_index); }
   for(int device=1;device<=4;device++){char name[20];snprintf(name,sizeof(name),"ATA Device %d",device);auto*ata=menu_child_named(ide,name);int row=ata->render_index,matches=0;for(int i=0;i<root_section_boundary_count;i++)if(root_section_boundaries[i]==row){assert(root_section_colors[i]==E64_MENU_DEVICE_SEPARATOR);matches++;}int adjacent=device>1&&(expanded==1||(expanded==2&&(device-1)%2));assert(matches==(ata->is_expanded||adjacent?1:0));}
  }
  // Exercise current production scrolling and Home on the complete deep tree.
  for(auto*n:after)if(n!=root&&n->type==FOLDER)n->is_expanded=1;
  menu_roots[0]=*root;current_menu=0;menu_cursor[0]=0;menu_window_top[0]=0;ui_traverse();int total=max_index[0];std::set<int> reached;
  for(int direction:{1,-1})for(int step=0;step<total+5;step++){
    ui_traverse();assert(ui_cursor_is_selectable(menu_cursor[0]));assert(menu_cursor[0]>=menu_window_top[0]&&menu_cursor[0]<menu_window_bottom[0]);reached.insert(menu_cursor[0]);
    int pixels=(menu_window_bottom[0]-menu_window_top[0])*8+ui_root_boundary_pixels(menu_window_top[0],menu_window_bottom[0]-1);assert(pixels<=200-E64_MENU_ROOT_TOP_INSET-E64_MENU_ROOT_BOTTOM_INSET);ui_move_cursor(direction);
  }
  assert(reached.count(0)&&reached.count(total-1));ui_key_action=42;ui_transparent=1;ui_transparent_layer=0;ui_render_current_item_only=1;renders=0;ui_return_to_root();assert(current_menu==0&&ui_enabled&&menu_cursor[0]==0&&renders==1&&ui_key_action==ACTION_None&&!ui_transparent&&ui_transparent_layer==-1);
  for(auto*n:after)if(n!=root&&n->type==FOLDER)assert(!n->is_expanded);

 }
}
'''
code=code.replace('#include <fstream>','#include <fstream>\n#include <sstream>').replace('@IDS@',','.join(ids)).replace('@PRODUCTION@',production).replace('@DRIVE@',drive).replace('@VIDEO@',video).replace('@MODEM@',modem)
code=code.replace('@DEFAULTS@','\n'.join(line for line in menu.splitlines() if line.startswith(('#define DEFAULT_VICII_', '#define DEFAULT_VIC_'))))
baseline=None
if args.baseline_archive:
 with tarfile.open(args.baseline_archive) as archive:
  old_menu=archive.extractfile('third_party/common/menu.c').read().decode()
  old_cfg=archive.extractfile('third_party/common/menu_configs.c').read().decode()
 old_drive=old_menu[old_menu.index('  drive_parent = ui_menu_add_folder(root, "Drives");'):old_menu.index('  parent = emux_add_cartridge_options(root);')]
 baseline=code[:code.index('int main(int argc,char**argv)')]
 baseline=baseline.replace(drive,old_drive)
 for name in ['base_name','update_autostart_label','add_item','build_configs_autostart_items','build_configs_drive_items']:
  baseline=baseline.replace(fn(cfg,name),fn(old_cfg,name))
 for name in ['menu_reorganize_video','menu_system_priority','menu_reorder_system']:
  baseline=baseline.replace(fn(menu,name),fn(old_menu,name))
 baseline+=r'''int main(int argc,char**argv){assert(argc==2);nodes.clear();auto*root=add(nullptr,-1,"root",FOLDER);auto*system=ui_menu_add_folder(root,(char*)"System");auto*network=ui_menu_add_folder(system,(char*)"Network");seed_modem(network);build_configs_autostart_items(system);ui_menu_add_toggle(MENU_AUTOSTART_WARP,system,(char*)"Autostart Warp",0);emux_add_machine_options(system);auto*roms=menu_child_named(system,"ROMs");build_power_menu(system);auto*power=menu_child_named(system,"Power");menu_item *global;auto*drives=seed_drives(root,&global);build_configs_drive_items(drives);emux_add_cartridge_options(root);menu_move_ieee488(root,drives,drives);auto*video=ui_menu_add_folder(root,(char*)"Video");ui_menu_add_button(MENU_CALC_TIMING,video,"Video Mode >");ui_menu_add_toggle(MENU_SCALING_INTERPOLATION,video,(char*)"Scaling Interpolation",1);ui_menu_add_toggle(MENU_USE_SCALING_PARAMS_0,video,(char*)"Apply Scaling Parameters At Boot",1);auto*shader=ui_menu_add_folder(video,(char*)"CRT Shader");ui_menu_add_toggle(MENU_SHADER_ENABLE,shader,(char*)"Enable CRT Shader?",1);auto*color=ui_menu_add_folder(video,(char*)"Color Adjustments");ui_menu_add_button(9004,color,"Reset");seed_video(video);menu_reorganize_storage(root,drives,global,system,network);menu_reorganize_video(video);menu_reorder_system(system);std::ofstream out(std::string(argv[1])+"/before.txt");dump(out,root);}
 '''
out=r/'build/menu-final-polish-hierarchy';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='e64-menu-reorg-') as tmp:
 t=Path(tmp)
 # Dump the current firmware's actual compile-time variant at the main path;
 # also exercise the optional IDE64 USB/network controls without enabling them.
 firmware_network=bool(re.search(r'^#define HAVE_NETWORK\b', (r/'third_party/vice-3.3/src/config.h').read_text(), re.M))
 for enabled in [not firmware_network,firmware_network]:
  destination=out if enabled==firmware_network else out/'optional-network-variant'
  destination.mkdir(exist_ok=True)
  variant=code if enabled else code.replace('#define HAVE_NETWORK 1','#undef HAVE_NETWORK')
  (t/'test.cpp').write_text(variant)
  subprocess.run(['g++','-std=c++17','-Wno-write-strings','-fsanitize=undefined','-I'+str(r/'third_party/common'),str(t/'test.cpp'),'-o',str(t/'test')],check=True)
  subprocess.run([str(t/'test'),str(destination)],check=True)
 if baseline is not None:
  (t/'before.cpp').write_text(baseline if firmware_network else baseline.replace('#define HAVE_NETWORK 1','#undef HAVE_NETWORK'))
  subprocess.run(['g++','-std=c++17','-Wno-write-strings','-fsanitize=undefined','-I'+str(r/'third_party/common'),str(t/'before.cpp'),'-o',str(t/'before')],check=True)
  subprocess.run([str(t/'before'),str(out)],check=True)
  def controls(path):return Counter(tuple(map(int,m)) for m in re.findall(r'\[(-?\d+),(-?\d+),(-?\d+)\]',path.read_text()) if int(m[0])>=0)
  old_controls=controls(out/'before.txt');new_controls=controls(out/'after.txt');removed_ids={ids.index(name) for name in ['MENU_DRIVE_REFERENCE','MENU_DRIVE_ROM_REFERENCE','MENU_IEEE488_HELP']}
  config_ids={ids.index(name) for name in ['MENU_CONFIGS_SELECT','MENU_CONFIGS_NEW','MENU_SAVE_SETTINGS','MENU_CONFIGS_RENAME','MENU_CONFIGS_PROTECTION','MENU_CONFIGS_DELETE','MENU_CONFIGS_RESTORE']}
  new_controls=Counter({k:v for k,v in new_controls.items() if k[0] not in config_ids})
  # First enum value is zero, matching the generated host fixture.
  old_controls=Counter({k:v for k,v in old_controls.items() if k[0] not in removed_ids})
  assert old_controls==new_controls,(old_controls-new_controls,new_controls-old_controls)
  (out/'baseline-controls.json').write_text(json.dumps({'same_control_ids_values_and_units':True,'functional_controls':sum(old_controls.values())},indent=2)+'\n')
print('PASS: production drive/REU/IDE64/ATA/RS-232/autostart/video construction; exact hierarchy, all original nodes reachable once, callback/range/value/sub_id preservation, 5 modem choices, per-drive independence, 10 screen adjustments, no resource writes, idempotent reorganization; Autostart grouping, cartridge ordering, native reference removal, collapsed/expanded/mixed Drive/ATA gray boundaries and Create Disk placement; actual firmware and optional IDE64 network variants; hierarchy dumps in '+str(out))
