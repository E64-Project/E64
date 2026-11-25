#!/usr/bin/env python3
"""Production fan callbacks plus UI actions/traversal/rendering; delayed save fixture."""
from pathlib import Path
import tempfile, subprocess
R=Path(__file__).resolve().parents[2]
ns={'__file__':str(R/'tools/menu_theme_test/run_tests.py')}
s=Path(ns['__file__']).read_text();exec(s[:s.index('with tempfile.TemporaryDirectory')],ns)
menu=(R/'third_party/common/menu.c').read_text();callbacks=menu[menu.index('static struct menu_item *fan_enabled_item'):menu.index('static void main_menu_cursor_listener')]
builder=menu[menu.index('  parent = ui_menu_add_folder(machine_parent, "Cooling Fan");'):menu.index('  parent = ui_menu_add_folder(machine_parent, "Network");')]
assert 'ui_menu_add_toggle' not in builder and 'ui_menu_add_read_only' not in builder
assert builder.count('ui_menu_add_range(')==2 and builder.count('ui_menu_add_button(')==1
assert 'fan_save_item->prefer_str = 1;' in builder
assert '"Fan On Temp"' in builder and '"Fan Off Temp"' in builder
fixture=r'''
#include "../../src/fan_control.h"
static FanStatus state;
static int errors;
void ui_error(const char *,...){++errors;}
void fan_get_status(FanStatus *s){*s=state;}
int fan_request(const FanSettings *p){
 if(state.pending || !fan_settings_valid(p))return -1;
 state.pending=1;return 0;
}
'''
fixture+='int fan_request_if_current(const FanSettings *p,const FanSettings *base){if(base->enabled!=state.settings.enabled||base->on_c!=state.settings.on_c||base->off_c!=state.settings.off_c)return 1;return fan_request(p); }\n'
# Use actual validation as well as actual menu/UI functions.
policy=(R/'src/fan_control.c').read_text();a=policy.index('int fan_settings_valid(');b=policy.index('\n}',a)+2
fixture+=policy[a:b]+'\n'+callbacks
case=r'''
static void fan_cursor_listener(menu_item*,int pos){fan_menu_cursor(pos);}
static void fan_navigation(){
 menu_item system,fan,on,off,save,network,logging;
 item(system,FOLDER,"System");system.is_expanded=1;
 item(fan,FOLDER,"Cooling Fan",9801);fan.is_expanded=1;fan.on_render=fan_menu_render;
 item(on,RANGE,"Fan On Temp",9802);item(off,RANGE,"Fan Off Temp",9803);
 item(save,BUTTON,"Save Fan Settings",9804);item(network,FOLDER,"Network");item(logging,FOLDER,"Logging");
 system.first_child=&fan;fan.first_child=&on;on.next=&off;off.next=&save;fan.next=&network;network.next=&logging;
 fan_enabled_item=&fan;fan_on_item=&on;fan_off_item=&off;fan_save_item=&save;save.on_value_changed=fan_menu_save;save.prefer_str=1;
 fan.on_open=fan_menu_next;fan.on_back=fan_menu_previous;on.on_value_changed=off.on_value_changed=fan_menu_changed;
 on.min=31;on.max=80;off.min=30;off.max=79;on.step=off.step=1;on.divisor=off.divisor=1;
 current_menu=0;menu_roots[0].first_child=&system;menu_roots[0].menu_height=200;menu_window_top[0]=0;
 state.available=1;state.settings={1,55,50};fan_menu_refresh();
 menu_roots[0].cursor_listener_func=fan_cursor_listener;

 ui_traverse();menu_cursor[0]=fan.render_index;ui_traverse();
 assert(!strcmp(fan.name,"Cooling Fan"));assert(!strcmp(fan.displayed_value,"Auto"));
 ui_action(ACTION_Return);ui_traverse();assert(!fan.is_expanded&&!fan_dirty);
 ui_action(ACTION_Return);ui_traverse();assert(fan.is_expanded&&!fan_dirty);
 for(const char *label:{"Off","On","Auto"}){
  ui_action(ACTION_Right);assert(!strcmp(fan.displayed_value,label));
  assert(fan_dirty&&fan.is_expanded&&!state.pending);
 }
 for(const char *label:{"On","Off","Auto"}){
  ui_action(ACTION_Left);assert(!strcmp(fan.displayed_value,label));
  assert(fan_dirty&&fan.is_expanded&&!state.pending);
 }
 fan_menu_discard();
 menu_cursor[0]=save.render_index;ui_traverse();ui_action(ACTION_Return);assert(state.pending&&!save.displayed_value[0]);
 state.pending=0;fan_menu_refresh();assert(!strcmp(save.displayed_value,"Saved"));
 clear_draws();int index=0;ui_render_children(&system,0,&index,0);bool saved_found=false;
 for(auto t:texts)if(t.text=="Saved"){saved_found=true;assert(t.color==E64_MENU_CONNECTED);assert(t.x+ui_text_width("Saved")==328);}assert(saved_found);

 // Real actions must preserve feedback across the fan/Network boundary.
 for(int action:{ACTION_Up,ACTION_Down,ACTION_Down,ACTION_Up,ACTION_Up,ACTION_Down}){
  ui_action(action);ui_traverse();assert(!strcmp(get_button_display_str(&save),"Saved"));
 }
 for(int n=0;n<20;n++){
  menu_cursor[0]=save.render_index;ui_traverse();
  ui_action(ACTION_Down);ui_traverse();assert(menu_cursor_item[0]==&network);
  assert(!strcmp(get_button_display_str(&save),"Saved"));
  ui_action(ACTION_Up);ui_traverse();assert(menu_cursor_item[0]==&save);
  assert(!strcmp(get_button_display_str(&save),"Saved"));
 }
 // Check both selection states, including the separate label color.
 for(auto selected:{&save,&off}){
  menu_cursor[0]=selected->render_index;ui_traverse();clear_draws();index=0;
  ui_render_children(&system,0,&index,0);bool status=false,label=false;
  for(auto t:texts){
   if(t.text=="Saved"){status=true;assert(t.color==E64_MENU_CONNECTED);}
   if(t.text=="Save Fan Settings"){label=true;assert(t.color==(selected==&save?E64_MENU_SELECTED_TEXT:E64_MENU_TEXT));}
  }
  assert(status&&label);
 }
 // Selected Saved retains E64 green; edits and failed saves leave it blank.
 menu_cursor[0]=save.render_index;ui_traverse();clear_draws();index=0;
 ui_render_children(&system,0,&index,0);saved_found=false;
 for(auto t:texts)if(t.text=="Saved"){saved_found=true;assert(t.color==E64_MENU_CONNECTED);}assert(saved_found);
 menu_cursor[0]=on.render_index;ui_traverse();ui_action(ACTION_Right);assert(!save.displayed_value[0]);assert(!get_button_display_str(&save)[0]);
 fan_menu_save(&save);assert(state.pending&&!save.displayed_value[0]);
 state.pending=0;state.error=1;fan_menu_refresh();assert(!save.displayed_value[0]&&fan_dirty);
 state.error=0;fan_menu_discard();
 for(auto row:{&on,&off})for(int dir:{1,-1}){
  state.settings={1,55,50};state.pending=0;fan_menu_discard();ui_traverse();menu_cursor[0]=row->render_index;ui_traverse();
  for(int n=0;n<4;n++){
   int old=row->value;ui_action(dir>0?ACTION_Right:ACTION_Left);assert(!state.pending);assert(row->value==old+dir);
   ui_traverse();assert(menu_cursor_item[0]==row && !row->disabled);
   fan_menu_refresh();ui_traverse();assert(menu_cursor_item[0]==row);
   char expected[16];snprintf(expected,sizeof(expected),"%d C",row->value);assert(!strcmp(ui_setting_value(row),expected));
   clear_draws();int index=0;ui_render_children(&system,0,&index,0);bool found=false;
   for(auto t:texts)if(t.text==expected){found=true;assert(t.x+ui_text_width(expected)==328);}assert(found);
  }
 }
 state.pending=0;fan_menu_refresh();menu_cursor[0]=off.render_index;ui_traverse();
 ui_action(ACTION_Down);ui_traverse();assert(menu_cursor_item[0]==&save);
 ui_action(ACTION_Return);ui_traverse();assert(state.pending&&menu_cursor_item[0]==&save);
 state.pending=0;fan_menu_refresh();ui_traverse();assert(menu_cursor_item[0]==&save);
 ui_action(ACTION_Down);ui_traverse();assert(menu_cursor_item[0]==&network);
 ui_action(ACTION_Down);ui_traverse();assert(menu_cursor_item[0]==&logging);
 ui_action(ACTION_Up);ui_traverse();assert(menu_cursor_item[0]==&network);
 ui_action(ACTION_Up);ui_traverse();assert(menu_cursor_item[0]==&save);
 for(auto row:{&on,&off})for(int dir:{1,-1}){
  state.settings={1,dir>0?80:31,dir>0?79:30};fan_menu_discard();menu_cursor[0]=row->render_index;ui_traverse();
  int old=row->value;ui_action(dir>0?ACTION_Right:ACTION_Left);ui_traverse();assert(row->value==old&&!state.pending&&menu_cursor_item[0]==row);
 }

 state.pending=0;state.error=0;fan_menu_save(&save);state.pending=0;fan_menu_refresh();
 assert(!strcmp(get_button_display_str(&save),"Saved"));
 menu_cursor[0]=fan.render_index;ui_traverse();ui_action(ACTION_Left);
 assert(!get_button_display_str(&save)[0]);
 fan_menu_discard();assert(!get_button_display_str(&save)[0]);
 menu_roots[0].cursor_listener_func=nullptr;
 state.available=0;fan_menu_refresh();assert(fan.disabled&&on.disabled&&off.disabled);
}
'''

ui=(R/'third_party/common/ui.c').read_text()
pixels=r"""
#define UI_USE_COMMON_MENU_FONT 1
#define FONT_NOTDEF_INDEX 0
#define BMC64_MACHINE_CLASS_C64 0
#define FB_LAYER_UI 0
static int emux_machine_class,ui_startup_error_font;
static uint8_t font8x8_basic[256][8],framebuffer[400*256];
static uint8_t *ui_fb=framebuffer;
static int ui_fb_pitch=400,ui_fb_w=400,ui_fb_h=256;
static uint32_t ui_vic_colors[16],uploaded[16];static int ui_vic_colors_valid;
static void circle_set_palette32_fbl(int,int i,uint32_t c){uploaded[i]=c;}
static void circle_update_palette_fbl(int){}
"""
pixels+='\n'+ns['function']('ui_draw_char')+'\n'+ns['function']('ui_draw_text_buf')+'\n'+ns['function']('ui_set_vic_palette')
palette=[line.split()[:3] for line in (R/'third_party/vice-3.3/data/C64/godot.vpl').read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
pixels+='\nstatic unsigned char rgb[]={'+','.join('0x'+c for row in palette for c in row)+'};\n'
pre=ns['pre'].replace('void ui_draw_text(const char *s,int x,int y,int color){texts.push_back({s,x,y,color});}',r"""
void ui_draw_text_buf(const char*,int,int,int,uint8_t*,int,int);
static void verify_pixels();
void ui_draw_text(const char *s,int x,int y,int color){
 texts.push_back({s,x,y,color});
 if(!strcmp(s,"Saved")||!strcmp(s,"Save Fan Settings")){
  verify_pixels();ui_draw_text_buf(s,0,0,color,nullptr,0,1);
  bool ink=false;
  for(int i=0;i<400*8;i++)if(framebuffer[i]!=255){
   ink=true;assert(framebuffer[i]==color);
   if(!strcmp(s,"Saved")){
    auto rgb=uploaded[framebuffer[i]];
    int r=(rgb>>16)&255,g=(rgb>>8)&255,b=rgb&255;
    assert(g>r&&g>b&&r<64);
   }
  }
  assert(ink);
 }
}
""")
# Deliver cursor notifications, as the native cursor_pos_updated() does.
pre=pre.replace("static void cursor_pos_updated(){}", "static void cursor_pos_updated(){if(menu_roots[current_menu].cursor_listener_func)menu_roots[current_menu].cursor_listener_func(&menu_roots[current_menu],menu_cursor[current_menu]);}")
# Keep framebuffer declarations before the capture stub, functions after shared helpers.
pre=pre.replace('void ui_draw_text_buf',pixels[:pixels.index('static void ui_draw_char(')]+'\nvoid ui_draw_text_buf',1)
pixfunc=pixels[pixels.index('static void ui_draw_char('):]+r"""
static void verify_pixels(){
 static uint8_t chargen[4096];memset(chargen,0x5a,sizeof(chargen));raw_video_font=chargen;
 memset(framebuffer,255,sizeof(framebuffer));ui_set_vic_palette(rgb,16);
}
"""
main=ns['power_test_main'].replace('int main(){',case+'\nint main(){fan_navigation();')
with tempfile.TemporaryDirectory(prefix='fan-nav-',dir=R/'build') as tmp:
 t=Path(tmp);(t/'theme-under-test.h').write_text(ns['THEME']);(t/'test.cpp').write_text(pre+ns['functions']+pixfunc+fixture+main)
 subprocess.run(['c++','-std=c++11','-Wno-sign-compare','-I'+str(R/'third_party/common'),str(t/'test.cpp'),'-o',str(t/'test')],check=True)
 subprocess.run([str(t/'test')],check=True)
print('PASS compact Cooling Fan structure, Return expansion, Left/Right Off/On/Auto cycling, blank/green Saved, selected/unselected framebuffer pixels and RGB, non-green labels, UP/DOWN status retention, failure and modification clearing; repeated ON/OFF +/- edits, pending redraw/focus, System navigation/Logging, limits, native Celsius alignment and existing renderer regressions')
