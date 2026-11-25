#!/usr/bin/env python3
"""Compile current native navigation functions; no firmware or SD writes."""
from pathlib import Path
import re,subprocess,tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'third_party/common/ui.c').read_text()
def fn(name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]
k=(root/'third_party/common/kbd.c').read_text()
# Physical Home must bypass raw key capture and joystick mapping in both directions.
for name in ['emu_key_pressed','emu_key_released']:
 part=k[k.index('void '+name+'('):];part=part[:part.index('\n}')]
 assert part.index('key == KEYCODE_Home')<part.index('raw_keycode_func')
 assert 'emu_ui_key_interrupt(key, '+('1' if name.endswith('pressed') else '0')+');' in part
pressed=fn('ui_key_pressed');assert pressed.index('KEYCODE_Home')<pressed.index('BMC64_NEW_KEYBOARD_INPUT')
released=fn('ui_key_released');assert re.search(r'case KEYCODE_Home:\s*return;',released)
code=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include "ui.h"
#include "menu_theme.h"
volatile int ui_enabled=1;
static int ui_external_owner,current_menu,ui_key_action,ui_transparent,ui_transparent_layer,ui_render_current_item_only;
enum {ACTION_None};
static menu_item menu_roots[NUM_MENU_ROOTS];
static int menu_cursor[NUM_MENU_ROOTS],menu_window_top[NUM_MENU_ROOTS],menu_window_bottom[NUM_MENU_ROOTS];
static int popped,rendered,committed;
static const menu_item *ui_text_cursor_field;
static void capture(long){committed++;}
static void (*raw_keycode_func)(long)=capture;
static int ui_row_pitch(int){return 8;}
static void ui_clear_menu(int n){menu_roots[n].first_child=nullptr;}
void ui_render_single_frame(){rendered++;}
FUNCTIONS
static void cancelled(menu_item*,menu_item*){popped++;}
int main(){
 // Root, first-level, deepest stack, file browser, confirmation, text entry.
 for(int scenario=0;scenario<6;scenario++){
  memset(menu_roots,0,sizeof(menu_roots));popped=rendered=committed=0;
  ui_enabled=1;ui_external_owner=0;raw_keycode_func=capture;
  current_menu=scenario==0?0:scenario==1?1:scenario==2?NUM_MENU_ROOTS-1:2;
  int depth=current_menu;
  menu_item heading{},first{},folder{},nested{},child{};
  heading.disabled=1;heading.next=&first;first.type=BUTTON;first.next=&folder;
  folder.type=FOLDER;folder.is_expanded=1;folder.first_child=&nested;
  nested.type=FOLDER;nested.is_expanded=1;nested.first_child=&child;
  menu_roots[0].first_child=&heading;menu_roots[0].menu_height=200;
  for(int i=1;i<=depth;i++)menu_roots[i].on_popped_off=cancelled;
  menu_cursor[0]=15;menu_window_top[0]=12;ui_key_action=42;
  ui_transparent=ui_render_current_item_only=1;ui_transparent_layer=2;
  ui_return_to_root();
  assert(current_menu==0&&ui_enabled==1&&menu_cursor[0]==1);
  assert(!folder.is_expanded&&!nested.is_expanded);
  assert(popped==depth&&rendered==1&&committed==0);
  assert(raw_keycode_func==nullptr&&ui_key_action==ACTION_None);
  assert(!ui_transparent&&!ui_render_current_item_only&&ui_transparent_layer==-1);
  assert(menu_window_top[0]==0&&menu_window_bottom[0]==20);
  assert(menu_roots[0].first_child==&heading);
 }
 ui_enabled=0;current_menu=2;rendered=0;raw_keycode_func=capture;
 ui_return_to_root();assert(current_menu==2&&rendered==0&&raw_keycode_func==capture);
 ui_enabled=1;ui_external_owner=1;ui_return_to_root();assert(current_menu==2&&rendered==0);
}
'''
names=['ui_text_cursor_reset','ui_item_at_index','ui_cursor_is_selectable','ui_refresh_menu_window','ui_select_first_interactive_item','ui_pop_menu','ui_collapse_folders','ui_return_to_root']
code=code.replace('FUNCTIONS','\n'.join(fn(n) for n in names))
with tempfile.TemporaryDirectory(prefix='e64-home-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-I'+str(root/'third_party/common'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: production Home root/first/deep/file/confirmation/text navigation, folder collapse, no commit, first selectable, root scrolling, key capture cancellation, closed/external guards and physical routing')
