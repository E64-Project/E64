#!/usr/bin/env python3
"""Execute production cartridge-default checks/dialog and Return-driven swaps."""
from pathlib import Path
import re,subprocess,tempfile
r=Path(__file__).resolve().parents[2];ui=(r/'third_party/common/ui.c').read_text();menu=(r/'third_party/common/menu.c').read_text();vice=(r/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
def fn(s,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]
ns={'__file__':str(r/'tools/menu_theme_test/run_tests.py')};s=Path(ns['__file__']).read_text();exec(s[:s.index('with tempfile.TemporaryDirectory')],ns)
pre=ns['pre'].replace('theme-under-test.h','menu_theme.h').replace('#include <cstring>','#include <cstring>\n#include <cstdarg>\n#include <deque>')
for line in [l for l in pre.splitlines() if l.startswith('static const char *menu_joystick_')]:pre=pre.replace(line,'')
case=menu[menu.index('  case MENU_MAKE_CART_DEFAULT: {'):menu.index('  case MENU_DETACH_DISK_8:',menu.index('  case MENU_MAKE_CART_DEFAULT: {'))]
swapcase=menu[menu.index('  case MENU_SWAP_JOYSTICKS:',menu.index('void menu_value_changed')):menu.index('  case MENU_JOYSTICK_PORT_1:',menu.index('  case MENU_SWAP_JOYSTICKS:',menu.index('void menu_value_changed')))]
extra={'MENU_MAKE_CART_DEFAULT','MENU_INFO_DIALOG','MENU_ERROR_DIALOG'}-set(ns['ids']);pre+='\nenum {'+','.join(k+'='+str(90000+i) for i,k in enumerate(sorted(extra)))+'};\n'
pre+=r'''
#define BMC64_MACHINE_CLASS_C64 0
#define CARTRIDGE_NONE -1
#define JOYDEV_NONE 0
static int emux_machine_class,exists=1,read_error,write_failure,set_calls,errors,renders,infos,ui_transparent_layer;
volatile int ui_enabled=1;
static std::string attached="/carts/valid.crt",saved,last_error;static int saved_type;
static const char *cartridge_current_filename(){return attached.empty()?nullptr:attached.c_str();}
static int util_file_exists(const char *p){assert(attached==p);return exists;}
static void cartridge_set_default(){set_calls++;if(write_failure){saved="";saved_type=CARTRIDGE_NONE;}else{saved=attached;saved_type=2;}}
static int resources_get_string(const char *key,const char **out){assert(!strcmp(key,"CartridgeFile"));*out=saved.c_str();return read_error?-1:0;}
static int resources_get_int(const char *key,int *out){assert(!strcmp(key,"CartridgeType"));*out=saved_type;return read_error?-1:0;}
static int joyswap,overlay_swap,joy_updates;
static struct {int device;} joydevs[2]={{10},{20}};
static menu_item *port_1_menu_item,*port_2_menu_item;
static int is_mouse_device(int){return 0;}
static void emux_set_joy_port_device(int,int){assert(false);}
static void overlay_joyswap_changed(int state){overlay_swap=state;}
static void ui_set_joy_items(){joy_updates++;}
'''
pre+='\n'+re.search(r'^#define DIALOG_LINE_CHARS .*$',ui,re.M).group()+'\n'+fn(vice,'emux_set_cart_default')+'\n'+fn(vice,'emux_try_set_cart_default')+'\n'+fn(menu,'menu_swap_joysticks')+'\n'+fn(menu,'menu_joystick_mapping')+'\n'+fn(menu,'menu_joystick_status')
# Fake memory-only allocator/OSD transport, real message wrapping/fitting/rendering.
helpers=r'''
static std::deque<menu_item> allocated;
static menu_item *add(menu_item*root,int type,const char*name,int id=-1){allocated.emplace_back();auto*p=&allocated.back();memset(p,0,sizeof(*p));p->type=(menu_item_type)type;p->id=id;p->prefer_str=1;p->menu_left=root->menu_left;p->menu_top=root->menu_top;p->menu_width=root->menu_width;p->menu_height=root->menu_height;snprintf(p->name,sizeof(p->name),"%s",name);auto**tail=&root->first_child;while(*tail)tail=&(*tail)->next;*tail=p;return p;}
menu_item *ui_menu_add_button(int id,menu_item*root,const char*name){return add(root,BUTTON,name,id);}
menu_item *ui_menu_add_divider(menu_item*root){return add(root,DIVIDER,"");}
static menu_item *ui_menu_add_read_only(menu_item*root,const char*name,menu_item_type type){auto*p=add(root,type,name);p->disabled=1;return p;}
menu_item *ui_menu_add_read_only_heading(menu_item*root,const char*name){return ui_menu_add_read_only(root,name,READ_ONLY_HEADING);}
menu_item *ui_push_menu(int width,int height){current_menu++;auto*p=&menu_roots[current_menu];memset(p,0,sizeof(*p));p->type=FOLDER;p->menu_width=width*8;p->menu_height=height*8;p->menu_left=16+(320-p->menu_width)/2;p->menu_top=24+(200-p->menu_height)/2;menu_window_top[current_menu]=0;menu_window_bottom[current_menu]=height;return p;}
void ui_enable_osd(){}
void glob_osd_popped(menu_item*,menu_item*){}
void ui_error(const char *format,...){errors++;last_error=format;}
void ui_render_single_frame(){renders++;ui_traverse();int n=0;ui_render_children(menu_roots[current_menu].first_child,current_menu,&n,0);}
'''
functions=ns['functions']+'\n'+helpers+'\n'+'\n'.join(fn(ui,n) for n in ['add_dialog_lines','ui_push_dialog_header','ui_fit_message_dialog','ui_info'])
main=ns['main'][:ns['main'].index('static void borders()')]+r'''
static void changed(menu_item *item){switch(item->id){@SWAP@ @CART@ default:assert(false);}}
static void root_action(menu_item&button,int id){current_menu=0;allocated.clear();item(button,BUTTON,id==MENU_SWAP_JOYSTICKS?"Swap Joysticks":"Action",id);button.on_value_changed=changed;button.prefer_str=1;menu_roots[0]=button;menu_roots[0].first_child=&button;menu_roots[0].menu_height=200;menu_cursor[0]=0;menu_window_top[0]=0;ui_traverse();clear_draws();}
int main(){
 menu_item button;
 for(int failure=0;failure<4;failure++){
  root_action(button,MENU_MAKE_CART_DEFAULT);attached=failure==0?"":"/carts/valid.crt";exists=failure!=1;read_error=failure==2;write_failure=failure==3;set_calls=errors=renders=0;saved="/carts/previous.crt";
  ui_action(ACTION_Return);assert(errors==1&&renders==0&&current_menu==0);assert(set_calls==(failure>=2?1:0));if(failure<2)assert(saved=="/carts/previous.crt");
 }
 root_action(button,MENU_MAKE_CART_DEFAULT);attached="/carts/valid.crt";exists=1;read_error=write_failure=0;set_calls=errors=renders=0;
 ui_action(ACTION_Return);assert(set_calls==1&&!errors&&renders==1&&saved==attached&&current_menu==1);
 auto&panel=menu_roots[1];assert(panel.menu_width==240&&panel.menu_height<=64);
 std::string message;int blank=0;for(auto*n=panel.first_child;n;n=n->next){message+=std::string(n->name)+" ";if(n->type==READ_ONLY_HEADING&&!n->name[0])blank++;}
 assert(message.find("Cartridge Set As Default")!=std::string::npos&&message.find("Save Your Config To Keep This Change.")!=std::string::npos&&blank==1);
 for(auto t:texts){assert(t.x>=panel.menu_left&&t.x+ui_text_width(t.text.c_str())<=panel.menu_left+panel.menu_width);assert(t.y>=panel.menu_top&&t.y+8<=panel.menu_top+panel.menu_height);}
 // Original Return dispatcher -> original swap handler -> live devices/status.
 root_action(button,MENU_SWAP_JOYSTICKS);joyswap=0;joydevs[0].device=10;joydevs[1].device=20;joy_updates=0;
 for(int state:{0,1,0,1,0}){
  assert(joyswap==state);clear_draws();int index=0;ui_render_children(&button,0,&index,0);
  // Label and status are separate draw calls, positioned by pixels rather
  // than a padded string. Keep exact wording and the standard right-aligned value edge.
  assert(texts.size()==2);
  assert(texts[0].text=="Swap Joysticks");
  assert(texts[1].text==(state?"Reversed 1=2, 2=1":"Normal 1=1, 2=2"));
  assert(ui_text_width(texts[1].text.c_str())==(state?17:15)*E64_MENU_CELL);
  assert(texts[0].x==button.menu_left+E64_MENU_ROW_MARGIN+E64_MENU_INDENT);
  assert(texts[1].x+ui_text_width(texts[1].text.c_str())==button.menu_left+button.menu_width-E64_MENU_ROW_MARGIN);
  assert(texts[0].x+ui_text_width(texts[0].text.c_str())+E64_MENU_CELL<=texts[1].x);
  assert(joydevs[0].device==(state?20:10)&&joydevs[1].device==(state?10:20));
  ui_action(ACTION_Return);assert(overlay_swap==joyswap&&joyswap==!state);
 }
 assert(joy_updates==5);
}
'''
main=main.replace('@CART@',case).replace('@SWAP@',swapcase)
assert len(re.findall(r'ui_menu_add_button\(MENU_SWAP_JOYSTICKS,',menu))==1
assert 'ui_menu_add_button(MENU_SWAP_JOYSTICKS, root, "Swap Joysticks")' in menu
for unit in range(8,12):
 assert f'MENU_ATTACH_DISK_{unit}, parent, "Attach Disk >"' in menu
 assert f'MENU_DETACH_DISK_{unit}, parent, "Remove Disk"' in menu
for label in ['Create Empty Disk >','Attach Tape >','Remove Tape','Create Empty Tape >']:assert '"'+label+'"' in menu
with tempfile.TemporaryDirectory(prefix='e64-menu-final-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(pre+'\n'+functions+'\n'+main)
 subprocess.run(['g++','-std=c++17','-Wno-write-strings','-fsanitize=undefined','-I'+str(r/'third_party/common'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: exact media image labels; one live swap action, real Return/swap/device/state rendering with the standard right-hand value column; checked default missing/file/readback/failure/success, unchanged underlying default call, compact real Info wrapping and save reminder without saving')
