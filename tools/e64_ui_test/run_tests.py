#!/usr/bin/env python3
"""Run production menu ordering/movement and live assignment descriptions."""
from pathlib import Path
import re, subprocess, tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'third_party/common/menu.c').read_text()
def function(name):
 m=re.search(r'^[\w *]+\b'+name+r'\([^;]*?\)\s*\{',source,re.M)
 assert m,name
 return source[m.start():source.index('\n}',m.end())+2]
funcs='\n'.join(function(n) for n in ['move_menu_item','menu_move_ieee488','menu_root_priority','menu_root_section','menu_reorder_root','menu_web_hotkey_label','show_drive_reference','show_drive_rom_reference','show_ieee488_help','menu_swap_joysticks','menu_joystick_mapping','menu_joystick_status'])
cart_source=(root/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text()
case=cart_source[cart_source.index('      case MENU_IEEE488:'):cart_source.index('      case MENU_REU:')]
# Keep the single original resource-backed toggle; no replacement controls.
assert len(re.findall(r'ui_menu_add_toggle\(\s*MENU_IEEE488\b',cart_source))==1
assert not re.search(r'ui_menu_add_toggle\(\s*MENU_IEEE488\b',source)
assert 'advanced_drive_parent = advanced;' in source
assert 'menu_move_ieee488(root, drive_parent, drive_parent);' in source
assert 'move_menu_item(folder, drive_parent, entry);' not in source
ids=sorted(set(re.findall(r'\bMENU_[A-Z0-9_]+',funcs)) | {'MENU_SWAP_JOYSTICKS'})
code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ui.h"
enum { IDS };
static struct menu_item *hotkey_cf1_item,*hotkey_cf3_item,*hotkey_cf5_item,*hotkey_cf7_item;
static struct menu_item *hotkey_tf1_item,*hotkey_tf3_item,*hotkey_tf5_item,*hotkey_tf7_item;

static struct menu_item help_root, help_rows[40];static int help_count,selected;
struct menu_item *ui_push_menu(int width,int height){
 memset(&help_root,0,sizeof(help_root));memset(help_rows,0,sizeof(help_rows));help_count=selected=0;
 help_root.menu_width=width*8;help_root.menu_height=height*8;
 help_root.menu_left=16+(320-width*8)/2;help_root.menu_top=24+(200-height*8)/2;return &help_root;
}
static struct menu_item *add_row(int id,struct menu_item *root,const char *name,int type){
 assert(help_count<40 && strlen(name)<MAX_MENU_STR);
 struct menu_item *row=&help_rows[help_count++];row->id=id;row->type=type;strcpy(row->name,name);
 if(help_count==1)root->first_child=row;else help_rows[help_count-2].next=row;return row;
}
struct menu_item *ui_menu_add_button(int id,struct menu_item *root,const char *name){return add_row(id,root,name,BUTTON);}
struct menu_item *ui_menu_add_read_only_heading(struct menu_item *root,const char *name){return add_row(-1,root,name,READ_ONLY_HEADING);}
struct menu_item *ui_menu_add_divider(struct menu_item *root){return add_row(-1,root,"",DIVIDER);}
void ui_select_first_interactive_item(void){selected++;}
static void verify_help(void){
 assert(selected==1);assert(help_count<=help_root.menu_height/8-1);
 assert(help_root.menu_left%8==0 && help_root.menu_top%8==0);
 for(int i=0;i<help_count;i++)assert(strlen(help_rows[i].name)<=35);
}

static int joyswap,overlay_swap,joy_items_calls,mouse_detaches;
static struct {int device;} joydevs[2];
static struct menu_item *port_1_menu_item,*port_2_menu_item;
enum {JOYDEV_NONE=0};
static int is_mouse_device(int device){return device==99;}
static void emux_set_joy_port_device(int port,int device){assert((port==1 || port==2) && device==JOYDEV_NONE);mouse_detaches++;}
static void overlay_joyswap_changed(int state){overlay_swap=state;}
static void ui_set_joy_items(void){joy_items_calls++;}
static int ieee_resource,ieee_rom_sets,ieee_error_count,ieee_fail_rom;
static int resources_set_string(const char *key,const char *value){assert(!strcmp(key,"IEEE488Image")&&!strcmp(value,"/carts/eprom.bin"));ieee_rom_sets++;return ieee_fail_rom?-1:0;}
static int resources_set_int(const char *key,int value){assert(!strcmp(key,"IEEE488"));ieee_resource=value;return 0;}
static int resources_get_int(const char *key,int *value){assert(!strcmp(key,"IEEE488"));*value=ieee_resource;return 0;}
void ui_error(const char *format,...){assert(format&&*format);ieee_error_count++;}
static void ieee_callback(struct menu_item *item){switch(item->id){@IEEE_CASE@ default:assert(0);}}
static int ieee_count(struct menu_item *item,int id){int n=0;for(;item;item=item->next){n+=item->id==id;n+=ieee_count(item->first_child,id);}return n;}
FUNCTIONS
static void ieee_relocation(void){
 for(int state=0;state<2;state++){
  struct menu_item root={0},cart={0},drives={0},advanced={0},units[4]={{0}},unit_options[4]={{0}},before={0},ieee={0},after={0},help={0},reference={0};
  strcpy(cart.name,"Cartridge");cart.type=drives.type=advanced.type=FOLDER;
  strcpy(advanced.name,"Advanced Drive Settings");
  root.first_child=&cart;cart.next=&drives;cart.first_child=&before;before.next=&ieee;ieee.next=&after;
  drives.first_child=&reference;reference.next=&help;help.next=&advanced;
  help.id=MENU_IEEE488_HELP;ieee.id=MENU_IEEE488;ieee.type=TOGGLE;
  strcpy(ieee.name,"IEEE-488 Interface");ieee.value=state;ieee.on_value_changed=ieee_callback;
  advanced.first_child=units;
  for(int i=0;i<4;i++){units[i].type=FOLDER;snprintf(units[i].name,sizeof(units[i].name),"Drive %d",8+i);units[i].first_child=&unit_options[i];if(i<3)units[i].next=&units[i+1];}
  struct menu_item original=ieee,original_help=help;
  ieee_resource=state;ieee_rom_sets=ieee_error_count=ieee_fail_rom=0;
  menu_move_ieee488(&root,&drives,&drives);
  assert(before.next==&after&&cart.first_child==&before&&reference.next==&advanced);
  assert(advanced.next==&ieee&&ieee.next==&help&&help.next==NULL&&units[3].next==NULL);
  original.next=ieee.next;original_help.next=help.next;
  assert(!memcmp(&original,&ieee,sizeof(ieee))&&!memcmp(&original_help,&help,sizeof(help)));
  assert(ieee_count(root.first_child,MENU_IEEE488)==1&&ieee_count(root.first_child,MENU_IEEE488_HELP)==1);
  assert(ieee_count(cart.first_child,MENU_IEEE488)==0);
  for(int i=0;i<4;i++){assert(units[i].first_child==&unit_options[i]);assert(ieee_count(units[i].first_child,MENU_IEEE488)==0);}
  assert(ieee_resource==state&&ieee_rom_sets==0&&ieee_error_count==0);
  menu_move_ieee488(&root,&drives,&drives); // Repeating cannot duplicate controls.
  assert(ieee_count(root.first_child,MENU_IEEE488)==1&&ieee.next==&help);
  // The untouched production IEEE case still controls the same global resource.
  ieee.value=!state;ieee.on_value_changed(&ieee);assert(ieee_resource==!state&&ieee.value==!state);
  ieee.value=state;ieee.on_value_changed(&ieee);assert(ieee_resource==state&&ieee_error_count==0);
  ieee_fail_rom=1;ieee.value=1;ieee.on_value_changed(&ieee);assert(ieee.value==0&&ieee_resource==0&&ieee_error_count==1);
 }
 // Other backends/missing target and Cartridge-without-IEEE remain unchanged.
 struct menu_item root={0},cart={0},child={0},drives={0},advanced={0};strcpy(cart.name,"Cartridge");root.first_child=&cart;cart.first_child=&child;
 menu_move_ieee488(&root,&drives,NULL);menu_move_ieee488(&root,&drives,&drives);assert(cart.first_child==&child&&!advanced.first_child);
}
int main(void) {
 ieee_relocation();
 struct menu_item root={0}, rows[16]={0};
 const char *names[]={"Video","Load & Run Disk >","Sound","Load Snapshot >","Save Snapshot >","System","Cartridge","Load Cartridge >","Load ROM Image >","Config: Default NTSC","Swap Joysticks","Warp Mode","Drives","","",""};
 int ids[]={-1,MENU_AUTOSTART,-1,MENU_LOAD_SNAP,MENU_SAVE_SNAP,-1,-1,MENU_C64_ATTACH_CART,MENU_LOAD_ROM_IMAGE,MENU_CONFIGS_SELECT,MENU_SWAP_JOYSTICKS,MENU_WARP_MODE,-1,-1,-1,-1};
 for(int i=0;i<16;i++){strcpy(rows[i].name,names[i]);rows[i].id=ids[i];rows[i].type=i<13?BUTTON:DIVIDER;if(i<15)rows[i].next=&rows[i+1];}
 root.first_child=rows;menu_reorder_root(&root);
 const int order[]={9,15,1,7,8,3,4,10,11};
 struct menu_item *item=root.first_child;
 for(unsigned i=0;i<sizeof(order)/sizeof(order[0]);i++){assert(item==&rows[order[i]]);item=item->next;}
 int count=0;for(item=root.first_child;item;item=item->next){assert(++count<=16);}
 assert(count==16);
 // Moving retains the original callback, value and subtree.
 struct menu_item from={0},to={0},first={0},second={0},child={0};
 from.first_child=&first;first.next=&second;first.first_child=&child;first.value=2;
 move_menu_item(&from,&to,&first);
 assert(from.first_child==&second && to.first_child==&first && first.next==NULL);
 assert(first.first_child==&child && first.value==2);
 move_menu_item(&from,&to,&first);assert(to.first_child==&first && first.next==NULL);
 // Each request observes changed menu assignments, without a Config reload.
 struct menu_item hotkey={0};hotkey.num_choices=2;strcpy(hotkey.choices[0],"None");strcpy(hotkey.choices[1],"Warp");hotkey_cf1_item=&hotkey;
 char label[36];menu_web_hotkey_label(0,label,sizeof(label));assert(!strcmp(label,"None"));
 hotkey.value=1;menu_web_hotkey_label(0,label,sizeof(label));assert(!strcmp(label,"Warp"));
 hotkey.value=99;menu_web_hotkey_label(0,label,sizeof(label));assert(!strcmp(label,"Unavailable"));
 menu_web_hotkey_label(8,label,sizeof(label));assert(!strcmp(label,"Unavailable"));

 joydevs[0].device=10;joydevs[1].device=20;assert(!strcmp(menu_joystick_mapping(),"1=1 / 2=2"));
 menu_swap_joysticks();assert(!strcmp(menu_joystick_status(),"Reverse")&&!strcmp(menu_joystick_mapping(),"1=2 / 2=1") && overlay_swap==1 && joydevs[0].device==20 && joydevs[1].device==10);
 menu_swap_joysticks();assert(!strcmp(menu_joystick_status()," Normal")&&!strcmp(menu_joystick_mapping(),"1=1 / 2=2") && overlay_swap==0 && joydevs[0].device==10 && joydevs[1].device==20 && joy_items_calls==2);
 struct menu_item mouse={0};mouse.choice_ints[0]=99;port_1_menu_item=&mouse;
 menu_swap_joysticks();assert(mouse_detaches==1 && !strcmp(menu_joystick_mapping(),"1=2 / 2=1"));
 puts("PASS: live joystick indicators follow actual device swaps, both states, overlay state and mouse-detach behavior");
 show_drive_reference();verify_help();assert(help_count==23);
 for(int i=0;i<help_count;i++)assert(strchr(help_rows[i].name,'*')==NULL);
 assert(!strncmp(help_rows[2].name,"Model    Image Capacity Mechanism",33));
 for(int i=4;i<=10;i++){assert(help_rows[i].name[9]=='.');assert(!strncmp(help_rows[i].name+24,"Single",6));}
 assert(!strncmp(help_rows[13].name,"2031",4) && !strncmp(help_rows[19].name,"SFD-1001",8));
 show_drive_rom_reference();verify_help();assert(help_count==24);
 assert(!strncmp(help_rows[5].name+9,"d1541II",7));assert(!strncmp(help_rows[5].name+22,"JD-d1541II",10));
 assert(!strncmp(help_rows[11].name+9,"dosCMDHD",8));
 show_ieee488_help();verify_help();assert(help_rows[help_count-1].id==MENU_DRIVE_ROM_REFERENCE);
 puts("PASS: native reference builders fit without scrolling/truncation, 8-pixel origins, four/three aligned columns, exact ROM case and linked IEEE Help");
 puts("PASS: single global IEEE-488 node directly in Drives, absent from Cartridge/advanced/per-drive folders; same callback/value, Help adjacency, idempotency, both resource states and ROM failure handling");
 puts("PASS: production Quick Access order and immediate Config divider; node identity/subtree preservation; live changed and unavailable hotkey assignments");
}
'''.replace('IDS',','.join(ids)).replace('FUNCTIONS',funcs).replace('@IEEE_CASE@',case)
with tempfile.TemporaryDirectory(dir=root/'build',prefix='e64-ui-') as tmp:
 p=Path(tmp);(p/'test.c').write_text(code)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(root/'third_party/common'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
