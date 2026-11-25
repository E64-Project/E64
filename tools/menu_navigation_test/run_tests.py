#!/usr/bin/env python3
"""Execute active C64 keymap lookup, real UI key dispatch and branch collapse.
All data are computer-only fixtures; no emulated keys or Config files written.
"""
from pathlib import Path
import re,subprocess,tempfile
r=Path(__file__).resolve().parents[2]
ui=(r/'third_party/common/ui.c').read_text();kbd=(r/'third_party/vice-3.3/src/keyboard.c').read_text();vice=(r/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
def fn(s,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]
# Share the production-renderer harness declarations, not its test results.
ns={'__file__':str(r/'tools/menu_theme_test/run_tests.py')};source=Path(ns['__file__']).read_text();exec(source[:source.index('with tempfile.TemporaryDirectory')],ns)
pre=ns['pre'].replace('theme-under-test.h','menu_theme.h').replace('#include <cstring>','#include <cstring>\n#include <cstdlib>\n#include <fstream>\n#include <sstream>\n#include "keycodes.h"')
pre+=r'''
static int keyboard_shift,ui_commodore_down,ui_transparent,ui_transparent_layer,ui_key_action;
static int ui_key_ticks,ui_key_ticks_next,ui_key_ticks_repeats,ui_key_ticks_repeats_next;
static int ui_external_owner,renders,finds,top_calls,keyboard_right_alt;
static int (*ui_collapse_key_query)(long,int,int);
static unsigned char ui_collapse_key_down[256];
volatile int ui_enabled=1;
enum {ACTION_None=10000};
void (*raw_keycode_func)(long);
long commodore_key_sym=KEYCODE_LeftControl;
#define INITIAL_ACTION_DELAY 10
#define INITIAL_ACTION_REPEAT_DELAY 10
static int test_shiftlock;
static int emu_get_keyboard_shiftlock(){return test_shiftlock;}
void ui_find_first(char){finds++;}
static int ui_keyboard_mapping;
static char menu_text_layout_key_to_char(long key,int shifted,int){return key==KEYCODE_6?(shifted?'^':'6'):key==KEYCODE_SingleQuote?'\'':0;}
void ui_to_top(){top_calls++;}
void ui_to_bottom(){}
void ui_page_up(){}
void ui_page_down(){}
static void ui_traverse(void);
void ui_render_single_frame(){renders++;ui_traverse();}
'''
# Keep matrix flags and lookup exactly as production; only the table loader is a fixture.
a=kbd.index('enum shift_type {');b=kbd.index('/* Is the resource code',a)
pre+='\n'+kbd[a:b]+'\nstatic keyboard_conv_t *keyconvmap;\nstatic int keyc_num,key_alternative;\n'
header=(r/'third_party/vice-3.3/src/keyboard.h').read_text();pre+='\n'.join(line for line in header.splitlines() if line.startswith('#define KBD_MOD_'))+'\n'
pre+='\n'+fn(kbd,'keyboard_key_is_unshifted_matrix')
pre+='\n#define BMC64_MACHINE_CLASS_C64 0\nstatic int emux_machine_class;\n'+fn(vice,'menu_c64_up_arrow_key')
keynames=(r/'third_party/common/kbd.c').read_text()
pre+='\n#define KCMP(x) (strcmp(keyname,x)==0)\n#define LEGACY_KCMP(x) KCMP(x)\n'+fn(keynames,'kbd_arch_keyname_to_keynum')
# Legacy text path is used here; the separate Config pixel suite exercises new UTF-8 editing.
type_legacy=fn(ui[ui.index('#else\nstatic void ui_type_char(char ch)'):],'ui_type_char')
functions=ns['functions']+'\n'+fn(ui,'ui_refresh_menu_window')+'\n'+fn(ui,'ui_collapse_folders')+'\n'+fn(ui,'ui_expanded_branch')+'\n'+fn(ui,'ui_collapse_current_branch')+'\n'+fn(ui,'ui_return_to_root')+'\n'+fn(ui,'ui_set_menu_collapse_key_query')+'\n'+fn(ui,'ui_delete_forward')+'\n'+type_legacy+'\n'+fn(ui,'ui_key_pressed')+'\n'+fn(ui,'ui_key_released')
main=ns['main'][:ns['main'].index('static void borders()')]+r'''
static std::vector<keyboard_conv_t> entries;
static void load(const char*path){
 entries.clear();std::ifstream in(path);assert(in);std::string line;
 while(std::getline(in,line)){
  std::istringstream row(line);std::string key;int r,c,flags;
  if(!(row>>key>>r>>c>>flags)||key[0]=='#')continue;
  long code=kbd_arch_keyname_to_keynum((char*)key.c_str());if(!code)continue;
  // The real loader replaces existing unconditional entries for the same key.
  bool replaced=false;
  for(auto&e:entries)if(e.sym==code&&!(e.shift&ALLOW_OTHER)&&!(e.shift&ALT_MAP)){e.row=r;e.column=c;e.shift=(shift_type)flags;replaced=true;break;}
  if(!replaced)entries.push_back({code,r,c,(shift_type)flags,nullptr});
 }
 keyconvmap=entries.data();keyc_num=entries.size();assert(keyc_num);
}
static menu_item nodes[9];
static void setup(int cursor){
 memset(menu_roots,0,sizeof(menu_roots));memset(nodes,0,sizeof(nodes));
 current_menu=0;ui_enabled=1;ui_external_owner=0;raw_keycode_func=nullptr;
 ui_key_action=ACTION_None;keyboard_shift=test_shiftlock=0;renders=finds=top_calls=0;
 memset(ui_collapse_key_down,0,sizeof(ui_collapse_key_down));
 for(int i=0;i<9;i++)item(nodes[i],i==3||i==5||i==8?BUTTON:FOLDER,"Node");
 // A -> B -> C -> action, sibling D -> action; unrelated E -> action.
 nodes[0].first_child=&nodes[1];nodes[0].next=&nodes[6];
 nodes[1].first_child=&nodes[2];nodes[1].next=&nodes[4];nodes[2].first_child=&nodes[3];nodes[4].first_child=&nodes[5];
 nodes[6].first_child=&nodes[7];nodes[7].first_child=&nodes[8];
 for(int i:{0,1,2,4,6,7})nodes[i].is_expanded=1;
 menu_roots[0]=nodes[0];menu_roots[0].first_child=&nodes[0];menu_roots[0].menu_height=200;
 menu_cursor[0]=cursor;menu_window_top[0]=0;menu_window_bottom[0]=20;
 ui_traverse();ui_set_menu_collapse_key_query(menu_c64_up_arrow_key);
}
int main(int argc,char**argv){assert(argc==2);
 std::string base=argv[1];
 load((base+"/sdcard/c64/rpi_pos.vkm").c_str());
 assert(menu_c64_up_arrow_key(KEYCODE_Delete,0,0));assert(!menu_c64_up_arrow_key(KEYCODE_Up,0,0));assert(!menu_c64_up_arrow_key(KEYCODE_Delete,1,0));
 setup(3);test_shiftlock=1;ui_key_pressed(KEYCODE_Delete);assert(nodes[2].is_expanded);
 for(int cursor:{2,3}){setup(cursor);ui_key_pressed(KEYCODE_Delete);assert(!nodes[2].is_expanded&&menu_cursor[0]==2);assert(nodes[0].is_expanded&&nodes[1].is_expanded&&nodes[4].is_expanded&&nodes[6].is_expanded&&nodes[7].is_expanded);assert(current_menu==0&&ui_enabled&&renders==1);ui_key_released(KEYCODE_Delete);}
 setup(1);ui_key_pressed(KEYCODE_Delete);assert(!nodes[1].is_expanded&&!nodes[2].is_expanded&&nodes[4].is_expanded&&nodes[6].is_expanded&&menu_cursor[0]==1);
 setup(0);ui_key_pressed(KEYCODE_Delete);assert(!nodes[0].is_expanded&&!nodes[1].is_expanded&&!nodes[2].is_expanded&&!nodes[4].is_expanded&&nodes[6].is_expanded&&nodes[7].is_expanded&&menu_cursor[0]==0);
 // A collapsed heading selects its nearest expanded parent, not the root.
 setup(1);nodes[2].is_expanded=0;menu_cursor[0]=2;ui_traverse();ui_key_pressed(KEYCODE_Delete);assert(!nodes[1].is_expanded&&nodes[0].is_expanded&&nodes[6].is_expanded&&menu_cursor[0]==1);
 // Root ordinary action has no applicable branch and remains open.
 setup(0);nodes[0].type=BUTTON;nodes[0].first_child=nullptr;ui_traverse();ui_key_pressed(KEYCODE_Delete);assert(nodes[6].is_expanded&&current_menu==0&&ui_enabled);
 // Neither modal file/confirmation menus nor text editors collapse a branch.
 for(int depth:{0,1,2}){
  setup(3);if(depth){current_menu=depth;menu_roots[depth]=menu_roots[0];menu_cursor[depth]=3;ui_traverse();}
  nodes[3].type=TEXTFIELD;strcpy(nodes[3].str_value,"ABC");nodes[3].value=1;nodes[3].max_length=32;
  ui_key_pressed(KEYCODE_Delete);assert(!strcmp(nodes[3].str_value,"AC")&&nodes[3].value==1&&nodes[2].is_expanded&&renders==0);
  ui_key_pressed(KEYCODE_6);assert(!strcmp(nodes[3].str_value,"A6C")&&nodes[2].is_expanded);
 }
 setup(3);current_menu=1;menu_roots[1]=menu_roots[0];menu_cursor[1]=3;ui_traverse();ui_key_pressed(KEYCODE_Delete);assert(current_menu==1&&nodes[2].is_expanded&&renders==0);
 setup(3);ui_key_pressed(KEYCODE_Up);assert(menu_cursor[0]==2&&nodes[2].is_expanded);ui_key_released(KEYCODE_Up);assert(ui_key_action==ACTION_None);
 setup(2);ui_key_released(KEYCODE_Return);assert(!nodes[2].is_expanded);ui_key_released(KEYCODE_Return);assert(nodes[2].is_expanded);
 setup(3);ui_key_pressed(KEYCODE_Home);assert(menu_cursor[0]==0&&current_menu==0&&ui_enabled);for(int i:{0,1,2,4,6,7})assert(!nodes[i].is_expanded);
 setup(3);ui_enabled=0;ui_collapse_current_branch();assert(nodes[2].is_expanded&&renders==0);
 // Resolve actual Maxi and Keyrah mappings without changing them.
 load((base+"/sdcard/c64/rpi_maxi_pos.vkm").c_str());assert(menu_c64_up_arrow_key(KEYCODE_SingleQuote,0,0)&&menu_c64_up_arrow_key(KEYCODE_Delete,0,0));setup(3);ui_key_pressed(KEYCODE_SingleQuote);assert(!nodes[2].is_expanded&&nodes[6].is_expanded);
 load((base+"/sdcard/c64/rpi_keyrah_v3_pos.vkm").c_str());assert(menu_c64_up_arrow_key(KEYCODE_BackSlash,0,0)&&!menu_c64_up_arrow_key(KEYCODE_Delete,0,0));setup(3);ui_key_pressed(KEYCODE_BackSlash);assert(!nodes[2].is_expanded);
 load((base+"/sdcard/c64/rpi_sym.vkm").c_str());assert(!menu_c64_up_arrow_key(KEYCODE_6,0,0)&&menu_c64_up_arrow_key(KEYCODE_6,1,0)&&!menu_c64_up_arrow_key(KEYCODE_6,1,1));setup(3);keyboard_shift=1;ui_key_pressed(KEYCODE_6);assert(!nodes[2].is_expanded);ui_key_released(KEYCODE_6);
 // German caret is also the UI's reserved back key: preserve Back priority.
 load((base+"/sdcard/c64/rpi_sym_de.vkm").c_str());assert(menu_c64_up_arrow_key(KEYCODE_BackQuote,0,0));setup(3);ui_key_pressed(KEYCODE_BackQuote);assert(nodes[2].is_expanded&&renders==0);
 emux_machine_class=1;assert(!menu_c64_up_arrow_key(KEYCODE_BackQuote,0,0));
 keyconvmap=nullptr;keyc_num=0;emux_machine_class=0;assert(!menu_c64_up_arrow_key(KEYCODE_Delete,0,0));
}
'''
# Compile both the shipping UTF-8 keyboard path and the retained legacy path.
layout=(r/'src/keyboard/keyboard_layout.c').read_text()
for modern in [False,True]:
 variant_pre=pre
 variant_functions=functions
 if modern:
  variant_pre=variant_pre.replace('#define BMC64_NEW_KEYBOARD_INPUT 0','#define BMC64_NEW_KEYBOARD_INPUT 1')
  variant_pre+='\nstatic MenuKeyboardLayout ui_keyboard_layout=KEYBOARD_LAYOUT_US;\n'+fn(layout,'keyboard_layout_has_altgr')+'\n'+fn(layout,'keyboard_layout_effective_shift')
  variant_pre+='\nstatic unsigned int ui_key_to_char(long key,int shifted){return menu_text_layout_key_to_char(key,shifted,0); }\n'
  variant_functions=variant_functions.replace(type_legacy,fn(ui,'ui_type_char'))
 with tempfile.TemporaryDirectory(prefix='e64-menu-navigation-') as tmp:
  p=Path(tmp);(p/'test.cpp').write_text(variant_pre+'\n'+variant_functions+'\n'+main)
  subprocess.run(['g++','-std=c++17','-Wno-write-strings','-fsanitize=undefined','-I'+str(r/'third_party/common'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test'),str(r)],check=True)
print('PASS: shipping and legacy UI key dispatch; active positional/Maxi/Keyrah/symbolic keymap lookup; nearest-branch and descendant-only collapse; unrelated sections preserved; heading selection; modal/text exclusions, Delete/typing, Home, cursor Up, Return and closed-UI guards; reserved Back priority')
