#!/usr/bin/env python3
"""Execute production border, selection and viewport rendering on a host."""
from pathlib import Path
import re,subprocess,tempfile,json
ROOT=Path(__file__).resolve().parents[2]
UI=(ROOT/'third_party/common/ui.c').read_text()
THEME=(ROOT/'third_party/common/menu_theme.h').read_text()
PREFERENCES=(ROOT/'third_party/common/menu.c').read_text()
usb_source=(ROOT/'third_party/common/menu_usb.c').read_text()
assert 'sprintf (usb_pref_item->name, "USB %d Direction >", dev+1);' in usb_source
assert 'ui_menu_add_multiple_choice(MENU_USB_0_PREF+dev, root, "")' in usb_source
assert 'usb_root = ui_push_menu(42, -1)' in PREFERENCES
pref_values=[]
for key in ['DRIVE_FLUSH_ON_DETACH','DRIVE_FLUSH_ON_WRITE','DRIVE_FLUSH_ON_WRITE_LOGGED']:
 match=re.search(r'strcpy\(drive_flush_item->choices\['+key+r'\],\s*"([^"]+)"\);',PREFERENCES)
 assert match,key
 pref_values.append(match.group(1))
assert pref_values==['On Detach','On Write','On Write (Logged)']
assert 'drive_flush_item->value = DRIVE_FLUSH_ON_WRITE;' in PREFERENCES
for value in ['Never','Always','On Activity']:
 assert '"'+value+'"' in PREFERENCES
expected_roles={'BACKGROUND':0,'TEXT':1,'SELECTED_TEXT':0,'HIGHLIGHT':3,'BORDER':14,'HEADER':7,'FOOTER':8,'SEPARATOR':9,'INTERNAL_SEPARATOR':11,'SUBMENU_SEPARATOR':9,'EXPANDABLE_SEPARATOR':11,'DEVICE_SEPARATOR':12,'CONNECTED':5,'DISCONNECTED':2}
for role,value in expected_roles.items():
 assert re.search(r'^#define E64_MENU_'+role+r' '+str(value)+r'[ \t]*(?:/\*[^\n]*\*/)?$',THEME,re.M),role
# Verify actual active C64 palette meanings, not just role names/numbers.
palette=[line.split()[:3] for line in (ROOT/'third_party/vice-3.3/data/C64/godot.vpl').read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
assert ''.join(palette[11]).upper()=='333333'
assert ''.join(palette[12]).upper()=='777777'
def function(name):
 m=re.search(r'^[\w *]+\b'+re.escape(name)+r'\([^;]*?\)\s*\{',UI,re.M)
 assert m,name
 return UI[m.start():UI.index('\n}',m.end())+2]
names=['ui_draw_c64_frame','ui_draw_c64_menu_frame','ui_draw_c64_panel','ui_draw_c64_horizontal_rule','ui_draw_c64_frame_divider','ui_menu_mark_option','ui_option_button_state','ui_is_option_button','ui_option_is_selected','ui_utf8_next','ui_text_cursor_reset','ui_text_cursor_on','ui_draw_text_cursor','ui_is_setting_value','ui_setting_value','ui_setting_value_x','ui_draw_setting_label','ui_row_pitch','ui_help_fixed_top','ui_help_fixed_bottom','ui_is_network_address_field','ui_network_value_item','ui_draw_network_value','ui_root_add_boundary_color','ui_root_add_boundary','ui_root_skip_rows','ui_root_collect_groups','ui_root_collect_boundaries','ui_root_boundary_pixels','ui_root_visible_bottom','ui_root_has_boundary','ui_draw_open_section_rule','ui_draw_raw_line','ui_menu_item_label','get_button_display_str','ui_measure_selection_popup','ui_fit_selection_popup','ui_render_children','ui_item_at_index','ui_cursor_is_selectable','ui_traverse_children','ui_traverse','ui_move_cursor','ui_select_first_interactive_item','do_on_value_changed','ui_action']
functions='\n\n'.join(function(n) for n in names)
ids=sorted(set(re.findall(r'\b(?:MENU_[A-Z0-9_]+|ACTION_[A-Za-z]+)',functions))-{'MENU_ID_DO_NOTHING'} | {'MENU_CONFIGS_SELECT','MENU_SAVE_EASYFLASH','MENU_POWER_REBOOT','MENU_POWER_OFF','MENU_CONFIRM_CANCEL','MENU_NETWORKING','MENU_NET_SAVE'})
pre=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
#include <set>
#include <utility>
#include "ui.h"
#include "../../src/configs/configs.h"
#include "theme-under-test.h"
enum { IDS };
#undef BMC64_NEW_KEYBOARD_INPUT
#define BMC64_NEW_KEYBOARD_INPUT 0
#define MAX_ROOT_SECTION_BOUNDARIES 128
static menu_item menu_roots[NUM_MENU_ROOTS];
static int current_menu,menu_cursor[NUM_MENU_ROOTS],max_index[NUM_MENU_ROOTS];
static int menu_window_top[NUM_MENU_ROOTS],menu_window_bottom[NUM_MENU_ROOTS];
static menu_item *menu_cursor_item[NUM_MENU_ROOTS];
static int ui_render_current_item_only;
static const menu_item *ui_text_cursor_field;
static int ui_text_cursor_position;
static uint32_t ui_text_cursor_hash;
static unsigned long ui_text_cursor_started, test_ticks;
static unsigned long circle_get_ticks(){return test_ticks;}
static int live_joyswap;
static const char *menu_joystick_mapping(){return live_joyswap ? "1=2 / 2=1" : "1=1 / 2=2";}
static const char *menu_joystick_status(){return live_joyswap ? "Reverse" : " Normal";}
struct ui_popup_measure {int marker_cells,symbol_cells,width;};
static void (*on_value_changed)(menu_item*);
static int osd_active;
menu_item *ui_pop_menu(){--current_menu;return &menu_roots[current_menu];}
void ui_pop_all_and_toggle(){current_menu=0;}
static void ui_toggle(){}
static int root_section_boundary_count,root_section_boundaries[MAX_ROOT_SECTION_BOUNDARIES],root_section_colors[MAX_ROOT_SECTION_BOUNDARIES];
uint8_t *raw_video_font=(uint8_t*)1;
struct Glyph {int code,x,y,color;};
struct Rect {int x,y,w,h,color,fill;};
struct Text {std::string text;int x,y,color;};
static std::vector<Glyph> glyphs;
static std::vector<Rect> rects;
static std::vector<Text> texts;
int ui_text_width(const char *s){return strlen(s)*E64_MENU_CELL;}
static void ui_draw_char_raw(int c,int x,int y,int color,void*,int,int){glyphs.push_back({c,x,y,color});}
void ui_draw_rect(int x,int y,int w,int h,int color,int fill){rects.push_back({x,y,w,h,color,fill});}
void ui_draw_text(const char *s,int x,int y,int color){texts.push_back({s,x,y,color});}
static void ui_draw_c64_menu_text(const char *s,int x,int y,int color,int){ui_draw_text(s,x,y,color);}
static void cursor_pos_updated(){}
'''.replace('IDS',','.join(ids))
main=r'''
static void clear_draws(){glyphs.clear();rects.clear();texts.clear();}
static void item(menu_item &m,int type,const char *name,int id=99999){
 memset(&m,0,sizeof(m));m.type=(menu_item_type)type;m.id=id;
 snprintf(m.name,sizeof(m.name),"%s",name);
 m.menu_left=16;m.menu_top=24;m.menu_width=320;m.menu_height=200;
}
static void borders(){
 for(int square:{0,1})for(int width:{16,24,80,320})for(int height:{16,24,96,200}){
  clear_draws();ui_draw_c64_frame(16,24,width,height,BORDER_COLOR,square);
  assert(rects.empty());
  assert(glyphs.size()==(unsigned)(2*(width/8)+2*(height/8)-4));
  assert(glyphs[0].code==(square?E64_MENU_SQUARE_TL:E64_MENU_ROUND_TL));
  assert(glyphs[1].code==(square?E64_MENU_SQUARE_TR:E64_MENU_ROUND_TR));
  assert(glyphs[2].code==(square?E64_MENU_SQUARE_BL:E64_MENU_ROUND_BL));
  assert(glyphs[3].code==(square?E64_MENU_SQUARE_BR:E64_MENU_ROUND_BR));
  std::set<std::pair<int,int>> positions;
  for(auto g:glyphs){
   assert(g.color==BORDER_COLOR && (g.x-16)%8==0 && (g.y-24)%8==0);
   assert(g.x>=16 && g.x<16+width && g.y>=24 && g.y<24+height);
   assert(positions.insert({g.x,g.y}).second); // No doubled border cells.
   if(g.x>16 && g.x<16+width-8)assert(g.code==E64_MENU_HORIZONTAL);
  }
 }
 clear_draws();ui_draw_c64_menu_frame(16,24,80,48,BORDER_COLOR);
 auto outer=glyphs;clear_draws();ui_draw_c64_menu_frame(24,32,64,32,BORDER_COLOR);
 for(int i=0;i<4;i++)assert(glyphs[i].code==outer[i].code); // Exact inner corners.
 clear_draws();ui_draw_c64_panel(16,24,80,48,0);
 assert(rects.size()==1 && rects[0].fill==1 && rects[0].color==BG_COLOR);
 assert(glyphs[0].code==E64_MENU_ROUND_TL);
 clear_draws();ui_draw_c64_frame_divider(16,32,80,BORDER_COLOR);
 assert(glyphs.size()==10 && glyphs.front().code==E64_MENU_LEFT_T && glyphs.back().code==E64_MENU_RIGHT_T);
 std::set<std::pair<int,int>> joins;for(auto g:glyphs)assert(joins.insert({g.x,g.y}).second);
 clear_draws();ui_draw_c64_frame(0,0,23,24,BORDER_COLOR,0);assert(glyphs.empty());
 raw_video_font=nullptr;ui_draw_c64_menu_frame(0,0,80,48,BORDER_COLOR);assert(glyphs.empty());raw_video_font=(uint8_t*)1;
}
static void markers(){
 menu_item options[3],action,folder,choice;
 for(int i=0;i<3;i++){item(options[i],BUTTON,"Choice");if(i<2)options[i].next=&options[i+1];}
 item(action,BUTTON,"Confirm");item(folder,FOLDER,"Open");
 strcpy(action.displayed_value,"  (*)");assert(ui_option_is_selected(&action));
 action.displayed_value[0]=0;assert(!ui_is_option_button(&action));
 ui_menu_mark_option(&action,0);action.displayed_value[0]=0;
 ui_menu_mark_option(&folder,1);assert(!ui_is_option_button(&folder));
 for(int selected=0;selected<3;selected++){
  for(int i=0;i<3;i++)ui_menu_mark_option(&options[i],i==selected);
  int count=0;for(auto &option:options){count+=ui_option_is_selected(&option);assert(!strcmp(option.name,"Choice"));}
  assert(count==1 && !ui_option_is_selected(&action) && !ui_option_is_selected(&folder));
 }
 item(choice,MULTIPLE_CHOICE,"Video");choice.num_choices=3;
 strcpy(choice.choices[0],"PAL");strcpy(choice.choices[1],"NTSC");strcpy(choice.choices[2],"Old NTSC");

 current_menu=0;menu_roots[0].first_child=&choice;menu_roots[0].menu_height=200;
 menu_window_top[0]=0;menu_window_bottom[0]=18;menu_cursor[0]=1;root_section_boundary_count=0;
 for(int v=0;v<3;v++){
  choice.value=v;clear_draws();int index=0;ui_render_children(&choice,0,&index,0);
  assert(texts.size()==2 && texts[1].text==choice.choices[v]);
  for(auto t:texts)assert(t.text!="*");
  assert(texts[1].x+ui_text_width(texts[1].text.c_str())==328 && texts[0].color==FG_COLOR);
 }
 current_menu=1;menu_roots[1].first_child=&options[0];menu_window_top[1]=0;menu_window_bottom[1]=10;
 menu_cursor[1]=2;clear_draws();int index=0;ui_render_children(&options[0],1,&index,0);
 int stars=0;for(auto t:texts)if(t.text==E64_MENU_OPTION_MARKER)stars++;
 assert(stars==1);assert(!rects.empty() && rects.back().color==HILITE_COLOR);
 for(auto t:texts)if(t.text==E64_MENU_OPTION_MARKER)assert(t.color==E64_MENU_SELECTED_TEXT);
 menu_roots[1].first_child=&action;menu_cursor[1]=0;clear_draws();index=0;ui_render_children(&action,1,&index,0);
 for(auto t:texts)assert(t.text!="*");
}
static void ordinary_values(){
 for(int stack:{0,1})for(int selected:{0,1})for(int v:{0,1}){
  current_menu=stack;menu_roots[stack].name[0]=0;menu_roots[stack].menu_height=200;
  menu_cursor[stack]=selected?0:1;menu_window_top[stack]=0;menu_window_bottom[stack]=18;root_section_boundary_count=0;
  for(const char *name:{"Warp Mode","IEEE-488 Interface","Virtual Devices","Dual SID"}){
   menu_item setting;item(setting,TOGGLE,name);setting.value=v;menu_roots[stack].first_child=&setting;
   clear_draws();int index=0;ui_render_children(&setting,stack,&index,0);
   assert(texts.size()==2 && texts[1].text==(v?"On":"Off"));
   for(auto t:texts){assert(t.text!="*");}
   assert(texts[1].x+ui_text_width(texts[1].text.c_str())==328);
  }
  for(const char *name:{"SID Model","SID2 Address","SID2 Model","Video Filter","Drive Model"}){
   menu_item setting;item(setting,MULTIPLE_CHOICE,name);setting.num_choices=2;setting.value=v;
   strcpy(setting.choices[0],!strcmp(name,"SID2 Address")?"0xde00":"8580");strcpy(setting.choices[1],"6581");menu_roots[stack].first_child=&setting;
   clear_draws();int index=0;ui_render_children(&setting,stack,&index,0);assert(texts.size()==2 && texts[1].text==setting.choices[v]);for(auto t:texts)assert(t.text!="*");
  }
  for(int type:{(int)CHECKBOX,(int)RANGE}){
   menu_item setting;item(setting,type,"Other Setting");setting.value=v;setting.divisor=1;menu_roots[stack].first_child=&setting;
   clear_draws();int index=0;ui_render_children(&setting,stack,&index,0);assert(texts.size()==2);for(auto t:texts)assert(t.text!="*");
  }
  menu_item protection;item(protection,BUTTON,v?"Protect The Current Config: On":"Protect The Current Config: Off",MENU_CONFIGS_PROTECTION);
  menu_roots[stack].first_child=&protection;
  clear_draws();int protection_index=0;ui_render_children(&protection,stack,&protection_index,0);
  assert(texts.size()==(v?3:2));
  assert(texts.front().color==(selected?E64_MENU_SELECTED_TEXT:E64_MENU_TEXT));
  if(v){assert(texts[1].text=="On"&&texts[1].color==E64_CONNECTED_COLOR);assert(texts[1].x==texts.front().x+ui_text_width("Protect The Current Config: "));}
  else assert(texts.front().text=="Protect The Current Config: Off");
  menu_item swap;item(swap,BUTTON,"Swap Joysticks",MENU_SWAP_JOYSTICKS);live_joyswap=v;menu_roots[stack].first_child=&swap;
  clear_draws();int index=0;ui_render_children(&swap,stack,&index,0);
  assert(texts.size()==2&&texts.front().text=="Swap Joysticks");
  assert(texts.back().text==(v?"Reversed 1=2, 2=1":"Normal 1=1, 2=2"));
  assert(ui_text_width(texts.back().text.c_str())==(v?17:15)*E64_MENU_CELL);
  assert(texts.back().x+ui_text_width(texts.back().text.c_str())==swap.menu_left+swap.menu_width-E64_MENU_ROW_MARGIN);
  const int label_x=texts.front().x;
  assert(label_x==swap.menu_left+(stack==0?E64_MENU_ROW_MARGIN:0)+E64_MENU_INDENT);
  assert(label_x+ui_text_width(texts.front().text.c_str())+E64_MENU_CELL<=texts.back().x);
  // Compare actual peer draw calls, in both states and root/popup contexts.
  for(const char *name:{"Load & Run Disk >","Load Snapshot >","Save Snapshot >","Load Cartridge >","Warp Mode"}){
   menu_item peer;item(peer,!strcmp(name,"Warp Mode")?TOGGLE:BUTTON,name);menu_roots[stack].first_child=&peer;
   clear_draws();int peer_index=0;ui_render_children(&peer,stack,&peer_index,0);
   assert(texts.front().text==name&&texts.front().x==label_x);
  }
 }
}
static void scroll(){
 menu_item rows[80];
 for(int i=0;i<80;i++){
  char name[32];snprintf(name,sizeof(name),"Row %d",i);item(rows[i],BUTTON,name);
  if(i<79)rows[i].next=&rows[i+1];
 }
 // At the unchanged 25-row frame, exactly two more real entries fit.
 current_menu=0;menu_roots[0].first_child=&rows[0];menu_roots[0].menu_height=200;
 menu_cursor[0]=0;menu_window_top[0]=0;ui_traverse();
 assert(menu_window_bottom[0]==20);
 assert(menu_window_bottom[0]-(200-(3+3+1)*8)/8==2);
 clear_draws();int first_index=0;ui_render_children(&rows[0],0,&first_index,0);
 assert(texts.size()==40 && texts.front().text=="Row 0" && texts[38].text=="Row 19");
 assert(texts.front().y==24+24-4 && texts.back().y+8==24+180);
 assert((24+200-16)-(texts.back().y+8)==4);
 // Short menus render only their real entries, with no inserted blanks.
 auto saved_next=rows[3].next;rows[3].next=nullptr;ui_traverse();
 assert(menu_window_top[0]==0&&menu_window_bottom[0]==4);
 clear_draws();first_index=0;ui_render_children(&rows[0],0,&first_index,0);assert(texts.size()==8);
 rows[3].next=saved_next;
 // Include disabled/divider rows; navigation must skip them unchanged.
 rows[7].type=DIVIDER;rows[15].disabled=1;
 for(int stack:{0,1}){
  current_menu=stack;menu_roots[stack].first_child=&rows[0];menu_roots[stack].menu_height=200;
  menu_cursor[stack]=0;menu_window_top[stack]=0;menu_window_bottom[stack]=25;
  std::set<int> reached;
  for(int direction:{1,-1})for(int step=0;step<85;step++){
   ui_traverse();assert(ui_cursor_is_selectable(menu_cursor[stack]));
   assert(menu_cursor[stack]>=menu_window_top[stack] && menu_cursor[stack]<menu_window_bottom[stack]);
   reached.insert(menu_cursor[stack]);clear_draws();int index=0;
   ui_render_children(&rows[0],stack,&index,0);assert(index==80);
   assert(rects.size()==1 && rects[0].color==HILITE_COLOR && rects[0].h==8);
   // Neither text nor highlighting reaches the root's header/footer rows.
   int start=24+(stack==0?20:8),end=24+(stack==0?184:200);
   for(auto t:texts)assert(t.y>=start && t.y+8<=end);
   for(auto g:glyphs)assert(g.y>=start && g.y+8<=end);
   assert(rects[0].y>=start && rects[0].y+8<=end);
   ui_move_cursor(direction);
  }
  assert(reached.count(0) && reached.count(79));
  assert(!reached.count(7) && !reached.count(15));
 }
 // Reference pages use normal selection navigation without fixed scrolling.
 current_menu=1;strcpy(rows[0].name,"DRIVE REFERENCE");
 menu_roots[1].first_child=&rows[0];menu_roots[1].menu_height=192;
 assert(ui_help_fixed_top(1)==0 && ui_help_fixed_bottom(1)==0);
 menu_cursor[1]=4;menu_window_top[1]=0;menu_window_bottom[1]=24;
 ui_move_cursor(1);assert(menu_cursor[1]==5);
 clear_draws();int index=0;ui_render_children(&rows[0],1,&index,0);
 assert(index==80 && !rects.empty());
 strcpy(rows[0].name,"Row 0");
 // Expanded folders reserve full-cell separators without hiding end items.
 current_menu=0;menu_roots[0].first_child=&rows[0];rows[0].type=FOLDER;rows[0].is_expanded=1;
 menu_item child;item(child,BUTTON,"Nested");rows[0].first_child=&child;
 menu_cursor[0]=0;menu_window_top[0]=0;menu_window_bottom[0]=18;ui_traverse();
 assert(root_section_boundary_count>0 && max_index[0]==81);
 menu_cursor[0]=80;ui_traverse();assert(menu_window_bottom[0]==81);
 // Expanded inline folders and section dividers obey the same physical viewport.
 for(int cursor=0;cursor<81;cursor++){
  menu_cursor[0]=cursor;ui_traverse();clear_draws();int rendered_index=0;
  ui_render_children(&rows[0],0,&rendered_index,0);
  for(auto t:texts)assert(t.y>=44&&t.y+8<=208);
  for(auto g:glyphs)assert(g.y>=44&&g.y+8<=208);
  for(auto h:rects)assert(h.y>=44&&h.y+h.h<=208);
 }
 rows[0].is_expanded=0;ui_traverse();assert(max_index[0]==80 && menu_cursor[0]==79);
}
static void separator_hierarchy_colors(){
 // Real renderer: explicit root section rules stay brown, internal rules gray.
 menu_item divider;item(divider,DIVIDER,"");current_menu=0;
 menu_roots[0]=divider;menu_roots[0].first_child=&divider;
 menu_roots[0].menu_height=200;menu_cursor[0]=1;
 menu_window_top[0]=0;menu_window_bottom[0]=18;root_section_boundary_count=0;
 for(int depth:{0,1,2,4}){
  clear_draws();int index=0;ui_render_children(&divider,0,&index,depth);
  assert(!glyphs.empty());for(auto g:glyphs){assert(g.code==E64_MENU_HORIZONTAL);assert(g.color==(depth?E64_MENU_EXPANDABLE_SEPARATOR:E64_MENU_SEPARATOR));}
 }
}
static int boundary_color(int row){
 int count=0,color=-1;
 for(int i=0;i<root_section_boundary_count;i++)if(root_section_boundaries[i]==row){color=root_section_colors[i];count++;}
 assert(count==1);return color;
}
static void hardware_separator_roles(){
 menu_item prefix,drives,d8,d9,attach,advanced,setting,other,tail;
 item(prefix,BUTTON,"Prefix");item(drives,FOLDER,"Drives");item(d8,FOLDER,"Drive 8");item(d9,FOLDER,"Drive 9");
 item(attach,BUTTON,"Attach Disk >");item(advanced,FOLDER,"Advanced Settings");item(setting,TOGGLE,"Setting");item(other,BUTTON,"Other");item(tail,BUTTON,"Tail");
 prefix.next=&drives;drives.next=&tail;drives.first_child=&d8;d8.next=&d9;d8.first_child=&attach;attach.next=&advanced;advanced.first_child=&setting;d9.first_child=&other;
 drives.is_expanded=d8.is_expanded=d9.is_expanded=advanced.is_expanded=1;
 current_menu=0;menu_roots[0]=prefix;menu_roots[0].first_child=&prefix;menu_roots[0].menu_height=200;menu_cursor[0]=0;menu_window_top[0]=0;ui_traverse();
 assert(boundary_color(drives.render_index)==E64_MENU_SEPARATOR);
 assert(boundary_color(d8.render_index)==E64_MENU_DEVICE_SEPARATOR);
 assert(boundary_color(advanced.render_index)==E64_MENU_EXPANDABLE_SEPARATOR);
 assert(boundary_color(d9.render_index)==E64_MENU_DEVICE_SEPARATOR);
 assert(boundary_color(tail.render_index)==E64_MENU_SEPARATOR);
 for(int i=1;i<root_section_boundary_count;i++)assert(root_section_boundaries[i]>root_section_boundaries[i-1]);
 // Shared boundaries retain the brighter role regardless of insertion order.
 root_section_boundary_count=0;
 ui_root_add_boundary_color(1,E64_MENU_EXPANDABLE_SEPARATOR);
 ui_root_add_boundary_color(1,E64_MENU_DEVICE_SEPARATOR);
 ui_root_add_boundary_color(1,E64_MENU_EXPANDABLE_SEPARATOR);
 assert(boundary_color(1)==E64_MENU_DEVICE_SEPARATOR);
 ui_root_add_boundary_color(1,E64_MENU_SEPARATOR);
 ui_root_add_boundary_color(1,E64_MENU_DEVICE_SEPARATOR);
 assert(boundary_color(1)==E64_MENU_SEPARATOR&&root_section_boundary_count==1);
 // Actual explicit separator glyphs within these sections use the dark role,
 // in both inline branches and separate native dialog/menu roots.
 for(const char*name:{"Network","Tape","Cartridge","Advanced Settings"})for(int stack:{0,1}){
  menu_item divider;item(divider,DIVIDER,"");current_menu=stack;menu_roots[stack]=divider;
  strcpy(menu_roots[stack].name,name);menu_roots[stack].first_child=&divider;
  menu_roots[stack].menu_height=200;menu_cursor[stack]=1;menu_window_top[stack]=0;menu_window_bottom[stack]=18;root_section_boundary_count=0;
  clear_draws();int index=0;ui_render_children(&divider,stack,&index,1);
  assert(!glyphs.empty());for(auto g:glyphs)assert(g.code==E64_MENU_HORIZONTAL&&g.color==(stack?E64_MENU_INTERNAL_SEPARATOR:E64_MENU_EXPANDABLE_SEPARATOR));
 }
}
static void submenu_group_rules(){
 menu_item root,a,b,c,child,other,divider;item(root,FOLDER,"Root");item(a,FOLDER,"A");item(b,FOLDER,"B");item(c,TOGGLE,"Setting");item(child,BUTTON,"Child");item(other,BUTTON,"Other");item(divider,DIVIDER,"");
 root.first_child=&a;root.is_expanded=1;a.next=&b;b.next=&c;a.first_child=&child;b.first_child=&other;
 current_menu=0;menu_roots[0]=root;menu_roots[0].first_child=&root;menu_roots[0].menu_height=200;menu_cursor[0]=0;menu_window_top[0]=0;
 for(int ea:{0,1})for(int eb:{0,1}){
  a.is_expanded=ea;b.is_expanded=eb;ui_traverse();
  int expected=ea+eb==2?3:ea+eb==1?2:0;assert(root_section_boundary_count==expected);
  for(int i=0;i<root_section_boundary_count;i++){assert(root_section_colors[i]==E64_MENU_EXPANDABLE_SEPARATOR);if(i)assert(root_section_boundaries[i]>root_section_boundaries[i-1]);}
  clear_draws();int index=0;ui_render_children(&root,0,&index,0);
  int rules=0;for(auto g:glyphs){assert(g.code==E64_MENU_HORIZONTAL&&g.color==E64_MENU_EXPANDABLE_SEPARATOR);rules++;}assert(rules==38*expected);
 }
 // Explicit divider shares the A/B boundary with both expanded groups.
 a.is_expanded=b.is_expanded=1;a.next=&divider;divider.next=&b;ui_traverse();assert(root_section_boundary_count==2);a.next=&b;
 // Collapsed child beneath an ordinary Remove row creates no inner line.
 a.is_expanded=1;b.is_expanded=0;a.first_child=&child;child.next=&divider;divider.type=FOLDER;divider.first_child=&other;divider.is_expanded=0;ui_traverse();
 for(int i=0;i<root_section_boundary_count;i++)assert(root_section_boundaries[i]!=divider.render_index);
 divider.is_expanded=1;ui_traverse();int opening=0;for(int i=0;i<root_section_boundary_count;i++)if(root_section_boundaries[i]==divider.render_index){assert(root_section_colors[i]==E64_MENU_EXPANDABLE_SEPARATOR);opening++;}assert(opening==1);
}
static void usability_label_widths(){
 menu_item row;current_menu=0;menu_roots[0].menu_height=200;
 menu_window_top[0]=0;menu_window_bottom[0]=18;menu_cursor[0]=1;root_section_boundary_count=0;
 for(const char *label:{"Select An Existing Config >","Create Config From Current Settings","Save Changes To The Current Config","Rename A Config >","Protect The Current Config: Off","Protect The Current Config: On","Delete An Existing Config >","Load Raw  8K >","Load Raw 16K >","Load Raw Ultimax >","Set Attached Cartridge as Default","Press Cartridge Freeze Button","Save EasyFlash Changes"}){
  item(row,BUTTON,label);row.prefer_str=1;row.menu_width=320;menu_roots[0].first_child=&row;
  clear_draws();int index=0;ui_render_children(&row,0,&index,1);
  assert(texts.size()==2&&texts[0].text==label&&texts[1].text.empty()&&texts[0].x+ui_text_width(label)<=row.menu_left+row.menu_width-8);
 }
 item(row,BUTTON,"Ultimax",MENU_C64_ATTACH_CART_ULTIMAX);row.prefer_str=1;row.menu_width=320;menu_roots[0].first_child=&row;
 clear_draws();int index=0;ui_render_children(&row,0,&index,1);assert(texts[0].text=="Load Raw Ultimax >"&&texts[0].x==row.menu_left+E64_MENU_ROW_MARGIN+2*E64_MENU_INDENT&&texts[0].x+ui_text_width(texts[0].text.c_str())<=row.menu_left+row.menu_width-8);

 for(int enabled:{0,1}){
  item(row,TOGGLE,"Apply Scaling Parameters At Boot");row.menu_width=320;row.id=MENU_USE_SCALING_PARAMS_0;row.value=enabled;
  strcpy(row.custom_toggle_label[0],"No");strcpy(row.custom_toggle_label[1],"Yes");menu_roots[0].first_child=&row;
  clear_draws();int index=0;ui_render_children(&row,0,&index,2);
  assert(texts.size()==2&&texts[0].text==row.name&&texts[1].text==(enabled?"Yes":"No"));
  assert(texts[0].x+ui_text_width(row.name)+8<=texts[1].x&&texts[1].x+ui_text_width(texts[1].text.c_str())==row.menu_left+312);
 }
}
static void cleanup_layouts(){
 menu_item setting;
 struct Sample {const char *label; int type; const char *value;};
 Sample cases[]={{"CMDHD Mode",MULTIPLE_CHOICE,"Initialization"},{"IEC Filesystem",TOGGLE,"On"},{"True Drive Emulation",TOGGLE,"Off"},{"Parallel Cable",MULTIPLE_CHOICE,"ProfessionalDOS"},{"RAM 2000",TOGGLE,"On"},{"RAM 4000",TOGGLE,"Off"},{"RAM 6000",TOGGLE,"On"},{"RAM 8000",TOGGLE,"Off"},{"RAM A000",TOGGLE,"On"},{"Virtual Devices",TOGGLE,"On"}};
 for(int width:{304,320})for(auto sample:cases){
  item(setting,sample.type,sample.label);setting.menu_width=width;
  if(sample.type==MULTIPLE_CHOICE){setting.num_choices=1;strcpy(setting.choices[0],sample.value);}
  else setting.value=!strcmp(sample.value,"On");
  current_menu=0;menu_roots[0].first_child=&setting;menu_roots[0].menu_height=200;
  menu_window_top[0]=0;menu_window_bottom[0]=18;menu_cursor[0]=1;root_section_boundary_count=0;
  clear_draws();int index=0;ui_render_children(&setting,0,&index,3);
  assert(texts.size()==2 && texts[0].text==sample.label && texts[1].text==sample.value);
  for(auto t:texts){assert(t.text!="*");}
  assert(texts[1].x+ui_text_width(texts[1].text.c_str())==setting.menu_left+width-8);
  assert(texts[0].x==setting.menu_left+40);
  assert(texts[0].x+ui_text_width(sample.label)+8<=texts[1].x);
 }
 // A deliberately overlong setting label is clipped on-screen, not allowed
 // to overwrite the complete value or its marker.
 item(setting,MULTIPLE_CHOICE,"An unusually long setting label");
 setting.num_choices=1;strcpy(setting.choices[0],"Configuration");
 current_menu=0;menu_roots[0].first_child=&setting;clear_draws();int index=0;
 ui_render_children(&setting,0,&index,3);
 assert(texts[0].text.back()=='>' && texts[0].x+ui_text_width(texts[0].text.c_str())+8<=texts[1].x);
 // Drive options reserve exactly one marker cell, with no embedded space.
 menu_item drive[3];const char *models[]={"1541II","1571","Auto"};
 for(int i=0;i<3;i++){item(drive[i],BUTTON,models[i]);drive[i].menu_width=96;drive[i].menu_height=80;if(i<2)drive[i].next=&drive[i+1];}
 for(int selected=0;selected<3;selected++){
  for(int i=0;i<3;i++)ui_menu_mark_option(&drive[i],i==selected);
  current_menu=1;menu_roots[1].first_child=&drive[0];menu_roots[1].menu_height=80;
  menu_cursor[1]=selected;menu_window_top[1]=0;menu_window_bottom[1]=9;
  clear_draws();index=0;ui_render_children(&drive[0],1,&index,0);
  int stars=0;for(auto t:texts){if(t.text=="*"){stars++;assert(t.x==16);}else if(t.text=="1541II"||t.text=="1571"||t.text=="Auto")assert(t.x==24);}
  assert(stars==1);
 }
 // Select Config uses two cells ("* "); categorized maximum-length names
 // and the default display alias fit without touching the right border.
 menu_item config;char maximum[CONFIGS_MAX_NAME_LEN+1];memset(maximum,'N',sizeof(maximum)-1);maximum[sizeof(maximum)-1]=0;
 for(const char *name:{(const char*)maximum,"Default NTSC"})for(int depth:{0,1})for(int selected:{0,1}){
  item(config,BUTTON,name,MENU_CONFIGS_SELECT_ITEM);config.menu_width=E64_MENU_CONFIG_LIST_COLS*8;config.menu_height=80;
  ui_menu_mark_option(&config,selected);menu_roots[1].first_child=&config;
  menu_cursor[1]=0;clear_draws();index=0;ui_render_children(&config,1,&index,depth);
  Text label=texts.back();assert(label.text==name && label.x==16+(depth+2)*8);
  assert(label.x+ui_text_width(name)<=16+config.menu_width-8);
  if(selected)assert(texts[0].text=="*" && texts[0].x+8==label.x);
 }
 // Full-length delete-list and restore rows fit their new list geometry.
 for(int id:{(int)MENU_CONFIGS_DELETE_ITEM,99999}){
  item(config,BUTTON,maximum,id);config.menu_width=E64_MENU_CONFIG_LIST_COLS*8;
  menu_roots[1].first_child=&config;clear_draws();index=0;ui_render_children(&config,1,&index,0);
  assert(texts[0].text==maximum && texts[0].x+256<=16+config.menu_width-8);
 }
 // Native input bar and caret at byte 32 stay inside the widened popup.
 menu_item dialog[3];item(dialog[0],READ_ONLY_HEADING,"New Config Name");
 item(dialog[1],DIVIDER,"");item(dialog[2],TEXTFIELD,"",MENU_CONFIGS_NEW_NAME);
 strcpy(dialog[2].str_value,maximum);dialog[2].value=CONFIGS_MAX_NAME_LEN;
 for(int i=0;i<3;i++){dialog[i].menu_width=E64_MENU_CONFIG_NAME_COLS*8;dialog[i].menu_height=40;if(i<2)dialog[i].next=&dialog[i+1];}
 strcpy(menu_roots[1].name,E64_MENU_CONFIG_NAME_TAG);
 menu_roots[1].first_child=&dialog[0];menu_cursor[1]=2;clear_draws();index=0;ui_render_children(&dialog[0],1,&index,0);
 bool full=false;for(auto t:texts)if(t.text==maximum){full=true;assert(t.x+256<=16+288-8);}
 assert(full);for(auto r:rects)assert(r.x>=16 && r.x+r.w<=16+288-8);
 menu_roots[1].name[0]=0;
 // Approved About wording, selectable License and whole CHARGEN cells.
 menu_item about[7];const char *lines[]={"E64 - v1.0","","DERIVED FROM","BMC64, VICE, & CIRCLE","For The Pi 3B+","","License >"};
 for(int i=0;i<7;i++){item(about[i],i==1||i==5?DIVIDER:i==6?BUTTON:READ_ONLY_HEADING,lines[i],i==6?MENU_LICENSE:99999);about[i].disabled=i!=6;about[i].menu_width=240;about[i].menu_height=88;if(i<6)about[i].next=&about[i+1];}
 strcpy(about[6].displayed_value," ");
 menu_roots[1].first_child=&about[0];menu_cursor[1]=6;menu_window_top[1]=0;menu_window_bottom[1]=10;clear_draws();index=0;ui_render_children(&about[0],1,&index,0);
 std::vector<Text> about_texts;for(auto t:texts){if(t.text.find_first_not_of(" ")!=std::string::npos)about_texts.push_back(t);}
 assert(about_texts.size()==5 && rects.size()==1 && menu_cursor_item[1]==&about[6]);
 int seen=0;for(int i:{0,2,3,4,6}){assert(about_texts[seen].text==lines[i]);assert(about_texts[seen].y==24+16+i*8);assert((about_texts[seen].x-16)%8==0 && about_texts[seen].x+ui_text_width(lines[i])<=16+240-8);seen++;}
 int upper_rule=0,lower_rule=0;for(auto g:glyphs){assert(g.color==E64_MENU_FOOTER && (g.y==24+24 || g.y==24+56));if(g.y==24+24)upper_rule++;else lower_rule++;}
 assert(upper_rule==24 && lower_rule==24);
 for(auto g:glyphs)assert(g.x>=16+24 && g.x<16+24+24*8 && (g.x-16)%8==0);
 assert(rects[0].x%8==0 && rects[0].w==ui_text_width("License >")+16);
 current_menu=1;menu_cursor_item[1]=&about[6];
 about[6].on_value_changed=[](menu_item *item){assert(item->id==MENU_LICENSE);current_menu++;};
 ui_action(ACTION_Return);assert(current_menu==2);current_menu=1;
 // License scrolling has no fixed header and reaches both ends of a long
 // document with the same viewport used for the complete reflowed GPL.
 menu_item license_rows[700];for(int i=0;i<700;i++){item(license_rows[i],BUTTON,"License text",MENU_TEXT);if(i<699)license_rows[i].next=&license_rows[i+1];}
 menu_roots[1].first_child=&license_rows[0];strcpy(menu_roots[1].name,"LICENSE");menu_roots[1].menu_height=200;
 menu_cursor[1]=0;menu_window_top[1]=0;menu_window_bottom[1]=25;
 for(int dir:{1,-1})for(int step=0;step<705;step++){ui_traverse();assert(menu_cursor[1]>=menu_window_top[1] && menu_cursor[1]<menu_window_bottom[1]);ui_move_cursor(dir);}
 ui_traverse();assert(menu_cursor[1]==0 && menu_window_top[1]==0);
}


static int chosen;
static void record_choice(menu_item *p){chosen=p->id;}
static void final_corrections(){
 // Active Config is a single CHARGEN label and never a competing right value.
 for(const char *label:{"Active Config: Default NTSC","Active Config: Default PAL"}) {
  memset(menu_roots,0,sizeof(menu_roots));
  menu_item active;item(active,FOLDER,label,MENU_CONFIGS_SELECT);
  strcpy(active.displayed_value,"Default NTSC"); // stale separate value must not overlap
  current_menu=0;menu_roots[0].first_child=&active;
  menu_cursor[0]=0;menu_window_top[0]=0;menu_window_bottom[0]=20;
  clear_draws();int index=0;ui_render_children(&active,0,&index,0);
  int labels=0;for(auto t:texts)if(t.text==label) {
   labels++;assert(t.x==active.menu_left+E64_MENU_ROW_MARGIN+E64_MENU_INDENT);
   assert(t.x+ui_text_width(label)<=active.menu_left+active.menu_width-E64_MENU_ROW_MARGIN);
   for(auto other:texts)if(other.text!=label && other.y==t.y)
    assert(other.x+ui_text_width(other.text.c_str())<=t.x || other.x>=t.x+ui_text_width(label));
  }
  assert(labels==1 && rects.size()==1);
  assert(rects[0].x==active.menu_left+E64_MENU_ROW_MARGIN);
  assert(rects[0].w==active.menu_width-2*E64_MENU_ROW_MARGIN);
 }

 menu_item rows[18];
 for(int opening=0;opening<3;opening++){
  memset(menu_roots,0,sizeof(menu_roots));
  for(int i=0;i<18;i++){item(rows[i],i<4?READ_ONLY_HEADING:BUTTON,"Disk type",1000+i);rows[i].menu_height=160;rows[i].on_value_changed=record_choice;if(i<17)rows[i].next=&rows[i+1];}
  rows[0].disabled=rows[2].disabled=1;
  strcpy(rows[0].name,"Create Empty Disk");rows[1].type=rows[3].type=DIVIDER;
  strcpy(rows[2].name," Type   Drive Model");
  current_menu=1;menu_roots[1].first_child=rows;menu_roots[1].menu_height=160;
  menu_window_top[1]=4;menu_window_bottom[1]=18;menu_cursor[1]=0;
  ui_select_first_interactive_item();assert(menu_cursor[1]==4);
  clear_draws();ui_traverse();assert(menu_cursor_item[1]==&rows[4]);
  int index=0;ui_render_children(rows,1,&index,0);
  assert(texts.front().y==24+8);assert(rects.size()==1 && rects[0].y==24+8+4*8);
  int bottom=0;for(auto t:texts)if(t.y+8>bottom)bottom=t.y+8;
  assert(24+160-bottom==8); // Balanced internal top/bottom inset.
  chosen=0;ui_action(ACTION_Return);assert(chosen==1004);
  ui_action(ACTION_Down);ui_traverse();assert(menu_cursor_item[1]==&rows[5]);
  ui_action(ACTION_Up);ui_traverse();assert(menu_cursor_item[1]==&rows[4]);
  ui_action(ACTION_Up);ui_traverse();assert(menu_cursor[1]==4);
  ui_action(ACTION_Escape);assert(current_menu==0);
 }
 for(int width:{304,320,336})for(int length:{2,3,6,8,32,35})for(int marker:{0,1})for(int symbol:{0,1}){
  memset(menu_roots,0,sizeof(menu_roots));item(menu_roots[0],FOLDER,"");menu_roots[0].menu_width=width;
  menu_item options[2];char label[36];memset(label,'A',length);label[length]=0;
  item(options[0],BUTTON,label);item(options[1],BUTTON,"B");options[0].next=&options[1];
  for(auto &o:options){strcpy(o.displayed_value," ");o.menu_height=80;if(marker)ui_menu_mark_option(&o,&o==options);if(symbol)o.symbol=31;}
  current_menu=1;item(menu_roots[1],FOLDER,"");auto *r=&menu_roots[1];r->menu_height=80;r->first_child=options;
  int fitted=ui_fit_selection_popup(r);int content=(length+marker+symbol)*8;
  if(content+24>width || content+24>320){assert(!fitted);continue;}
  assert(fitted && r->menu_width>=content+24);
  assert(2*r->menu_left+r->menu_width==2*menu_roots[0].menu_left+width);
  assert((r->menu_width-content-8)%16==0);
  menu_window_top[1]=0;menu_window_bottom[1]=9;menu_cursor[1]=0;
  clear_draws();int index=0;ui_render_children(options,1,&index,0);
  assert(rects.size()==1 && rects[0].w==content);
  int old_columns=(content+16)/8;
  if(old_columns<6)old_columns=6;
  if((old_columns-content/8)%2)++old_columns;
  int old_padding=(old_columns*8-content)/2;
  assert(r->menu_width==(old_columns+1)*8);
  assert(rects[0].x-r->menu_left==old_padding);
  assert(r->menu_left+r->menu_width-(rects[0].x+content)==old_padding+8);
  for(auto t:texts)if(t.text.find_first_not_of(' ')!=std::string::npos){assert(t.x>=rects[0].x && t.x+ui_text_width(t.text.c_str())<=rects[0].x+content);}
  for(auto g:glyphs)if(g.code==31){assert(g.x==rects[0].x);assert(g.x+8<=rects[0].x+content);}
  int before=r->menu_width;assert(ui_fit_selection_popup(r) && before==r->menu_width);
 }
 // Actual Drive Model's longest label keeps its marker directly adjacent.
 memset(menu_roots,0,sizeof(menu_roots));item(menu_roots[0],FOLDER,"");
 menu_item model;item(model,BUTTON,"1541II");ui_menu_mark_option(&model,1);
 item(menu_roots[1],FOLDER,"");menu_roots[1].menu_height=80;menu_roots[1].first_child=&model;
 assert(ui_fit_selection_popup(&menu_roots[1]) && menu_roots[1].menu_width==80);
 current_menu=1;menu_window_top[1]=0;menu_window_bottom[1]=9;menu_cursor[1]=0;
 clear_draws();int model_index=0;ui_render_children(&model,1,&model_index,0);
 assert(texts.size()==2 && texts[0].text=="*" && texts[1].text=="1541II");
 assert(texts[0].x+8==texts[1].x && texts[0].x-model.menu_left==8);
 assert(model.menu_left+model.menu_width-(texts[1].x+48)==16);
 // Actual arrow-bearing Change Drive ROM labels include their trailing arrow.
 memset(menu_roots,0,sizeof(menu_roots));item(menu_roots[0],FOLDER,"");
 menu_item arrow;item(arrow,BUTTON,"1541II >");strcpy(arrow.displayed_value," ");item(menu_roots[1],FOLDER,"");
 auto *r=&menu_roots[1];r->first_child=&arrow;r->menu_height=80;
 assert(ui_fit_selection_popup(r) && r->menu_width==88);
 clear_draws();int arrow_index=0;ui_render_children(&arrow,1,&arrow_index,0);
 assert(texts[0].text=="1541II >" && texts[0].x-r->menu_left==8);
 assert(r->menu_left+r->menu_width-(texts[0].x+64)==16);
 assert(rects.size()==1 && rects[0].x==texts[0].x && rects[0].w==64);
 // Visible appended values are measured in addition to names/decorations.
 strcpy(arrow.displayed_value,"ROM");r->name[0]=0;
 assert(ui_fit_selection_popup(r) && r->menu_width==(8+1+3+2+1)*8);
 strcpy(arrow.displayed_value," ");
 // Explicit exclusions: info/confirm, file browser, and full-height panels.
 for(int id:{(int)MENU_CONFIRM_OK,(int)MENU_INFO_DIALOG}){r->name[0]=0;arrow.id=id;assert(!ui_fit_selection_popup(r));}
 arrow.id=99999;arrow.sub_id=MENU_SUB_SELECT_VOLUME;assert(!ui_fit_selection_popup(r));
 arrow.sub_id=0;r->menu_height=200;assert(!ui_fit_selection_popup(r));
 // SD and USB use the same rounded panel path; all four corners match main.
 clear_draws();ui_draw_c64_menu_frame(16,24,320,200,BORDER_COLOR);auto main_corners=glyphs;
 for(const char *volume:{"SD","USB1","USB2","USB3"}){
  (void)volume;clear_draws();ui_draw_c64_panel(16,24,320,200,0);
  for(int i=0;i<4;i++)assert(glyphs[i].code==main_corners[i].code);
 }
}


static void autostart_value_alignment(){
 for(int stack:{0,1})for(const char *value:{"None","Boot Disk.d64","demo.prg"}){
  current_menu=stack;menu_roots[stack].name[0]=0;menu_roots[stack].menu_height=200;
  menu_cursor[stack]=1;menu_window_top[stack]=0;menu_window_bottom[stack]=18;root_section_boundary_count=0;
  menu_item status;item(status,BUTTON,"Current Autostart",MENU_ID_DO_NOTHING);
  status.disabled=1;status.prefer_str=1;strcpy(status.displayed_value,value);
  menu_roots[stack].first_child=&status;clear_draws();int index=0;
  ui_render_children(&status,stack,&index,0);
  assert(texts.size()==2&&texts[0].text=="Current Autostart"&&texts[1].text==value);
  assert(texts[1].x+ui_text_width(value)==328);
  assert(texts[0].x+ui_text_width("Current Autostart")<texts[1].x);
  assert(!ui_cursor_is_selectable(0)&&!status.on_value_changed);
 }
}

static int power_action_calls,power_cancel_calls,network_open_calls,network_save_calls;
static void power_action(menu_item*){power_action_calls++;}
static void power_dispatch(menu_item *m){assert(m->id==MENU_CONFIRM_CANCEL);power_cancel_calls++;ui_pop_menu();}
static void network_dispatch(menu_item *m){if(m->id==MENU_NETWORKING)network_open_calls++;else if(m->id==MENU_NET_SAVE)network_save_calls++;else assert(false);}

static int rom_choice;
static void rom_dispatch(menu_item*m){rom_choice=m->id;}
static void compact_rom_selection(){
 const char *labels[]={"LOAD ROM IMAGE","","Load Raw  8K >","Load Raw 16K >","Load Raw Ultimax >"};
 for(int parent:{0,1}){
  assert(parent==0||parent==1);
  current_menu=0;menu_roots[0].menu_left=0;menu_roots[0].menu_top=16;menu_roots[0].menu_width=320;menu_roots[0].menu_height=208;
  auto*r=ui_push_menu(22,7);strcpy(r->name,"E64 ROM Selection");
  assert(r->menu_width==176&&r->menu_height==56&&r->menu_left==72&&r->menu_top==92);
  assert(2*r->menu_left+r->menu_width==320&&2*r->menu_top+r->menu_height==240);
  menu_item rows[5];for(int n=0;n<5;n++){
   item(rows[n],n==0?READ_ONLY_HEADING:n==1?DIVIDER:BUTTON,labels[n],200+n);
   rows[n].disabled=n==0;rows[n].menu_left=r->menu_left;rows[n].menu_top=r->menu_top+8;rows[n].menu_width=r->menu_width;rows[n].menu_height=r->menu_height;
   rows[n].prefer_str=1;if(n<4)rows[n].next=&rows[n+1];
  }
  r->first_child=rows;max_index[1]=5;root_section_boundary_count=0;on_value_changed=rom_dispatch;
  ui_select_first_interactive_item();assert(menu_cursor[1]==2);
  for(int selected:{2,3,4}){
   menu_cursor[1]=selected;clear_draws();ui_draw_c64_panel(r->menu_left-8,r->menu_top-8,r->menu_width+16,r->menu_height+16,0);
   int index=0;ui_render_children(rows,1,&index,0);assert(index==5);
   int visible=0;for(auto t:texts)if(!t.text.empty()){
    if(t.text==labels[0])assert(2*t.x+ui_text_width(t.text.c_str())==2*r->menu_left+r->menu_width);
    else assert(t.x==r->menu_left+8);
    assert(t.x>=r->menu_left+8&&t.x+ui_text_width(t.text.c_str())<=r->menu_left+r->menu_width-8);
    assert(t.y>=r->menu_top+8&&t.y+8<=r->menu_top+r->menu_height-8);visible++;
   }assert(visible==4);
   int bars=0,borders=0;for(auto g:glyphs){if(g.color==E64_MENU_SEPARATOR){assert(g.code==E64_MENU_HORIZONTAL&&g.y==r->menu_top+16);bars++;}else{assert(g.color==BORDER_COLOR);borders++;}}assert(bars==20&&borders>0);
   int highlights=0;for(auto rect:rects)if(rect.color==HILITE_COLOR){assert(rect.x==r->menu_left+8&&rect.w==r->menu_width-16&&rect.y==r->menu_top+8+selected*8&&rect.h==8);highlights++;}assert(highlights==1);
   const char*dir=getenv("E64_POWER_PREVIEW_DRAW_DIR");
   if(dir&&E64_MENU_BORDER==14&&E64_MENU_TEXT==1){char path[1024];snprintf(path,sizeof(path),"%s/rom-choice-%d.draw",dir,selected-1);FILE*f=fopen(path,"w");assert(f);for(auto v:rects)fprintf(f,"R %d %d %d %d %d %d\n",v.x,v.y,v.w,v.h,v.color,v.fill);for(auto v:glyphs)fprintf(f,"G %d %d %d %d\n",v.code,v.x,v.y,v.color);for(auto v:texts)if(!v.text.empty())fprintf(f,"T %d %d %d %s\n",v.x,v.y,v.color,v.text.c_str());fclose(f);}
   rom_choice=0;ui_action(ACTION_Return);assert(rom_choice==200+selected);
  }
  menu_cursor[1]=2;ui_action(ACTION_Down);assert(menu_cursor[1]==3);ui_action(ACTION_Down);assert(menu_cursor[1]==4);ui_action(ACTION_Up);assert(menu_cursor[1]==3);ui_action(ACTION_Escape);assert(current_menu==0);
  // Untagged dialogs retain the original internal divider color.
  current_menu=1;r->name[0]=0;clear_draws();int index=0;ui_render_children(rows,1,&index,0);int brown=0;for(auto g:glyphs)if(g.color==E64_MENU_SEPARATOR)brown++;assert(!brown);
 }
}
static void power_confirmations(){
 for(int off:{0,1}){
  current_menu=0;menu_roots[0].menu_left=0;menu_roots[0].menu_top=24;
  menu_roots[0].menu_width=320;menu_roots[0].menu_height=192;
  auto*r=ui_push_menu(16,6);strcpy(r->name,"E64 Power Confirm");
  assert(r->menu_width==128&&r->menu_height==48&&r->menu_left==96&&r->menu_top==96);
  assert(2*r->menu_left+r->menu_width==320&&r->menu_left%8==0&&r->menu_top%8==0);
  menu_item rows[4];item(rows[0],READ_ONLY_HEADING,off?"SHUTDOWN":"REBOOT");rows[0].disabled=1;
  item(rows[1],DIVIDER,"");item(rows[2],BUTTON,off?"Shutdown Now":"Reboot Now",off?MENU_POWER_OFF:MENU_POWER_REBOOT);
  item(rows[3],BUTTON,"Cancel",MENU_CONFIRM_CANCEL);rows[2].on_value_changed=power_action;
  for(int n=0;n<4;n++){rows[n].menu_left=r->menu_left;rows[n].menu_top=r->menu_top;rows[n].menu_width=r->menu_width;rows[n].menu_height=r->menu_height;if(n<3)rows[n].next=&rows[n+1];}
  rows[2].prefer_str=rows[3].prefer_str=1;r->first_child=rows;max_index[1]=4;root_section_boundary_count=0;
  on_value_changed=power_dispatch;power_action_calls=power_cancel_calls=0;ui_select_first_interactive_item();assert(menu_cursor[1]==2);
  for(int selected:{2,3}){
   menu_cursor[1]=selected;clear_draws();
   ui_draw_c64_panel(r->menu_left-8,r->menu_top-8,r->menu_width+16,r->menu_height+16,0);
   int index=0;ui_render_children(rows,1,&index,0);assert(index==4);
   int visible=0;for(auto t:texts)if(!t.text.empty()){
    assert(2*t.x+ui_text_width(t.text.c_str())==2*r->menu_left+r->menu_width);
    assert(t.x%8==0&&t.y%8==0&&t.x>=r->menu_left+8&&t.x+ui_text_width(t.text.c_str())<=r->menu_left+r->menu_width-8);
    assert(t.y==r->menu_top+8+(visible==0?0:visible+1)*8);
    if(visible==0)assert(t.text==(off?"SHUTDOWN":"REBOOT")&&t.color==E64_MENU_HEADING);
    else assert(t.color==((selected==visible+1)?E64_MENU_SELECTED_TEXT:E64_MENU_TEXT));
    visible++;
   }assert(visible==3);
   int bars=0,borders=0;for(auto g:glyphs){if(g.color==E64_MENU_SEPARATOR){assert(g.code==E64_MENU_HORIZONTAL&&g.y==r->menu_top+16);bars++;}else {assert(g.color==BORDER_COLOR);borders++;}}
   assert(bars==14&&borders>0);
   int highlights=0;for(auto rect:rects)if(rect.color==HILITE_COLOR){assert(rect.x==r->menu_left+8&&rect.w==r->menu_width-16&&rect.y==r->menu_top+8+selected*8&&rect.h==8);highlights++;}assert(highlights==1);
   const char*dir=getenv("E64_POWER_PREVIEW_DRAW_DIR");
   if(dir&&E64_MENU_BORDER==14&&E64_MENU_TEXT==1){
    char path[1024];snprintf(path,sizeof(path),"%s/%s-%s.draw",dir,off?"shutdown":"reboot",selected==2?"action":"cancel");FILE*f=fopen(path,"w");assert(f);
    for(auto v:rects)fprintf(f,"R %d %d %d %d %d %d\n",v.x,v.y,v.w,v.h,v.color,v.fill);
    for(auto v:glyphs)fprintf(f,"G %d %d %d %d\n",v.code,v.x,v.y,v.color);
    for(auto v:texts)if(!v.text.empty())fprintf(f,"T %d %d %d %s\n",v.x,v.y,v.color,v.text.c_str());
    fclose(f);
   }
  }
  // Real cursor/Return/Escape dispatch; never invoke a power action on entry.
  ui_select_first_interactive_item();assert(menu_cursor[1]==2&&!power_action_calls&&!power_cancel_calls);
  ui_action(ACTION_Down);assert(menu_cursor[1]==3);ui_action(ACTION_Up);assert(menu_cursor[1]==2);
  clear_draws();int index=0;ui_render_children(rows,1,&index,0);ui_action(ACTION_Return);assert(power_action_calls==1&&!power_cancel_calls);
  ui_action(ACTION_Down);index=0;ui_render_children(rows,1,&index,0);ui_action(ACTION_Return);assert(current_menu==0&&power_cancel_calls==1&&power_action_calls==1);
  current_menu=1;ui_select_first_interactive_item();index=0;ui_render_children(rows,1,&index,0);ui_action(ACTION_Escape);assert(current_menu==0&&power_action_calls==1);
  // Without the private tag, an otherwise identical dialog keeps generic layout.
  current_menu=1;r->name[0]=0;menu_cursor[1]=2;clear_draws();index=0;ui_render_children(rows,1,&index,0);
  bool found_action=false;for(auto t:texts)if(t.text==(off?"Shutdown Now":"Reboot Now")){assert(t.x==r->menu_left+8&&t.y==r->menu_top+16);found_action=true;}assert(found_action);
  for(auto g:glyphs)assert(g.color==E64_MENU_INTERNAL_SEPARATOR);
  r->first_child=nullptr;current_menu=0;on_value_changed=nullptr;
 }
}
static void network_safe_entry(){
 menu_item network,save,status,device;item(network,FOLDER,"Network",MENU_NETWORKING);item(save,BUTTON,"Save Network Settings & Reboot",MENU_NET_SAVE);item(status,READ_ONLY_HEADING,"Network Status:");status.disabled=1;item(device,MULTIPLE_CHOICE,"Network Device");
 network.first_child=&save;save.next=&status;status.next=&device;device.num_choices=1;strcpy(device.choices[0],"Off");
 current_menu=0;menu_roots[0]=network;menu_roots[0].first_child=&network;menu_cursor[0]=0;menu_window_top[0]=0;menu_window_bottom[0]=24;network_open_calls=network_save_calls=0;on_value_changed=network_dispatch;
 ui_traverse();assert(menu_cursor_item[0]==&network);
 ui_action(ACTION_Return);assert(network.is_expanded&&menu_cursor[0]==0&&network_open_calls==1&&!network_save_calls);
 ui_traverse();assert(menu_cursor_item[0]==&network);
 ui_action(ACTION_Return);assert(!network.is_expanded&&menu_cursor[0]==0&&network_open_calls==2&&!network_save_calls);
 ui_action(ACTION_Return);assert(network.is_expanded&&menu_cursor[0]==0&&!network_save_calls);
 ui_traverse();assert(menu_cursor_item[0]!=&save);on_value_changed=nullptr;menu_roots[0].first_child=nullptr;
}


static void preferences_title_case_values(){
 const char *values[]={@PREF_VALUES@};
 for(int stack:{0,1})for(int choice=0;choice<3;choice++)for(int selected:{0,1}){
  menu_item row;item(row,MULTIPLE_CHOICE,"Disk Write Mode");row.num_choices=3;row.value=choice;
  for(int i=0;i<3;i++)strcpy(row.choices[i],values[i]);
  current_menu=stack;menu_roots[stack].name[0]=0;menu_roots[stack].menu_height=200;
  menu_roots[stack].first_child=&row;menu_cursor[stack]=selected?0:1;
  menu_window_top[stack]=0;menu_window_bottom[stack]=18;root_section_boundary_count=0;
  clear_draws();int index=0;ui_render_children(&row,stack,&index,0);
  assert(texts.size()==2&&texts[0].text=="Disk Write Mode"&&texts[1].text==values[choice]);
  assert(texts[1].x+ui_text_width(values[choice])==328);
  assert(texts[0].x+ui_text_width("Disk Write Mode")+16<=texts[1].x);
  assert(row.value==choice&&row.num_choices==3);
 }
}

static int easyflash_ui_saves;
static void easyflash_ui_dispatch(menu_item*m){assert(m->id==MENU_SAVE_EASYFLASH);easyflash_ui_saves++;}
static void easyflash_disabled_ui(){
 for(int stack:{0,1})for(int attached:{0,1}){
  menu_item before,save,after;item(before,BUTTON,"Before");item(save,BUTTON,"Save EasyFlash Changes",MENU_SAVE_EASYFLASH);item(after,BUTTON,"After");before.next=&save;save.next=&after;save.disabled=!attached;save.prefer_str=1;
  current_menu=stack;menu_roots[stack].name[0]=0;menu_roots[stack].first_child=&before;menu_roots[stack].menu_height=200;
  menu_cursor[stack]=0;menu_window_top[stack]=0;menu_window_bottom[stack]=18;max_index[stack]=3;root_section_boundary_count=0;
  ui_move_cursor(1);assert(menu_cursor[stack]==(attached?1:2));
  menu_cursor[stack]=0;clear_draws();int index=0;ui_render_children(&before,stack,&index,0);bool found=false;
  for(auto t:texts){if(t.text=="Save EasyFlash Changes"){assert(t.color==(attached?FG_COLOR:DISABLED_COLOR));found=true;}}
  assert(found);
  menu_cursor_item[stack]=&save;on_value_changed=easyflash_ui_dispatch;easyflash_ui_saves=0;ui_action(ACTION_Return);assert(easyflash_ui_saves==attached);on_value_changed=nullptr;
 }
}
static void native_file_size_rows(){
 for(const char *size:{"0 B","4 KB","8 KB","16 KB","171 KB","1.0 MB","4.00 GB"})for(int selected:{0,1})for(int top:{0,1}){
  menu_item row;int available=38-(int)strlen(size)-1;
  std::string label(available,'A');item(row,BUTTON,label.c_str());strcpy(row.str_value,"original-full-filename.rom");strcpy(row.displayed_value,size);
  current_menu=1;menu_roots[1].name[0]=0;menu_roots[1].first_child=&row;menu_roots[1].menu_height=200;
  menu_cursor[1]=selected?top:top+1;menu_window_top[1]=top;menu_window_bottom[1]=top+18;
  clear_draws();int index=top;ui_render_children(&row,1,&index,0);
  assert(texts.size()==2&&texts[0].text==label&&texts[1].text==size);
  assert(texts[0].x==24&&texts[1].x+ui_text_width(size)==328);
  assert(texts[0].x+ui_text_width(row.name)+8<=texts[1].x);
  assert(texts[0].x%8==0&&texts[1].x%8==0);
  assert(texts[0].color==(selected?E64_MENU_SELECTED_TEXT:FG_COLOR));
  assert(texts[1].color==texts[0].color);
  if(selected){assert(!rects.empty());auto h=rects.back();assert(h.x==24&&h.w==304&&h.color==HILITE_COLOR);}
  else assert(rects.empty());
  assert(!strcmp(row.str_value,"original-full-filename.rom"));
 }
 menu_roots[1].first_child=nullptr;
}

static void round2_usb_direction_labels(){
 for(int port=0;port<4;port++)for(int choice=0;choice<3;choice++){
  menu_item row;char label[40];snprintf(label,sizeof(label),"USB %d Direction >",port+1);
  int ids[]={MENU_USB_0_PREF,MENU_USB_1_PREF,MENU_USB_2_PREF,MENU_USB_3_PREF};
  item(row,MULTIPLE_CHOICE,label,ids[port]);row.menu_width=42*8;
  strcpy(row.choices[0],"Analog+POTX/Y Buttons");strcpy(row.choices[1],"Hat+POTX/Y Buttons");strcpy(row.choices[2],"Hat+POTX/Y Paddles");row.value=choice;
  current_menu=1;menu_roots[1].name[0]=0;menu_roots[1].first_child=&row;menu_roots[1].menu_height=200;
  menu_cursor[1]=1;menu_window_top[1]=0;menu_window_bottom[1]=18;
  clear_draws();int index=0;ui_render_children(&row,1,&index,0);
  assert(texts[0].text==label);assert(texts[0].x==row.menu_left+8);
  assert(texts[0].x+ui_text_width(label)+8<=texts[1].x);
  assert(texts[1].x+ui_text_width(texts[1].text.c_str())==344);
 }
 menu_roots[1].first_child=nullptr;
}
static void round1_network_and_rom_metadata(){
 menu_item row;item(row,READ_ONLY_HEADING,"Network Status:");assert(ui_network_value_item(&row));
 strcpy(row.displayed_value,"Connected");row.disabled=1;
 current_menu=0;menu_roots[0].first_child=&row;menu_cursor[0]=1;menu_window_top[0]=0;menu_window_bottom[0]=18;
 clear_draws();int status_index=0;ui_render_children(&row,0,&status_index,1);
 assert(texts.size()==3&&texts[0].text=="Network Status"&&texts[1].text==": ");
 assert(texts[1].x==row.menu_left+22*8&&texts[2].x==row.menu_left+24*8);
 assert(texts[2].text=="Connected"&&texts[2].color==E64_MENU_HEADING);
 for(int id:{MENU_NETWORK_ENABLED,MENU_NET_IP_MODE,MENU_NET_IP_ADDRESS,MENU_NET_NETMASK,MENU_NET_GATEWAY,MENU_NET_DNS,MENU_NET_NTP_ENABLED,MENU_NET_NTP_SERVER,MENU_TIMEZONE_OFFSET,MENU_NET_DST_ENABLED,MENU_WIFI_SECURITY,MENU_WIFI_COUNTRY,MENU_WEBUI_ENABLED,MENU_WEBUI_PIN}){
  item(row,TOGGLE,"Daylight Savings",id);row.value=1;
  current_menu=0;menu_roots[0].first_child=&row;menu_roots[0].name[0]=0;root_section_boundary_count=0;
  menu_cursor[0]=1;menu_window_top[0]=0;menu_window_bottom[0]=18;clear_draws();int index=0;ui_render_children(&row,0,&index,0);
  assert(texts.size()==3&&texts[0].text=="Daylight Savings"&&texts[1].text==": ");
  assert(texts[1].x==row.menu_left+22*8);
  assert(texts[2].x==texts[1].x+16);
  assert(texts[0].x+ui_text_width(row.name)<=texts[1].x);
  assert(texts[1].x%8==0&&texts[2].x%8==0);
 }
 for(int id:{MENU_NET_IP_ADDRESS,MENU_NET_NETMASK,MENU_NET_GATEWAY,MENU_NET_DNS,MENU_NET_NTP_SERVER})for(int indent:{0,1,2,3,4}){
  item(row,TEXTFIELD,"Subnet Mask",id);strcpy(row.str_value,"255.255.255.255");
  current_menu=0;menu_roots[0].first_child=&row;menu_cursor[0]=1;
  clear_draws();int index=0;ui_render_children(&row,0,&index,indent);
  assert(texts[0].text=="Subnet Mask"&&texts[0].x+ui_text_width(row.name)<=texts[1].x);
  assert(texts[1].x==row.menu_left+22*8&&texts[2].x==row.menu_left+24*8);
  assert(texts[2].text=="255.255.255.255"&&texts[2].x+15*8==328);
 }
 item(row,TEXTFIELD,"Wi-Fi SSID",MENU_WIFI_SSID);strcpy(row.str_value,"An extremely long wireless network name beyond the border");
 current_menu=0;menu_roots[0].first_child=&row;menu_cursor[0]=1;clear_draws();int index=0;ui_render_children(&row,0,&index,0);
 assert(texts.back().text.back()=='>'&&texts.back().x+ui_text_width(texts.back().text.c_str())<=328);
 // Selected ROM metadata is left aligned, so a fitted long filename cannot
 // collide with its right-aligned size. Other headings stay centered.
 item(row,READ_ONLY_HEADING,"a-long-selected-file.rom");row.menu_width=272;
 strcpy(row.str_value,"a-long-selected-file.rom");strcpy(row.displayed_value,"16 KB");
 current_menu=1;strcpy(menu_roots[1].name,"E64 ROM Selection");menu_roots[1].first_child=&row;menu_roots[1].menu_height=72;
 menu_cursor[1]=1;menu_window_top[1]=0;menu_window_bottom[1]=9;clear_draws();index=0;ui_render_children(&row,1,&index,0);
 assert(texts.size()==2&&texts[0].x==24&&texts[0].text==row.name);
 assert(texts[0].x+ui_text_width(row.name)+8<=texts[1].x);
 menu_roots[1].first_child=nullptr;menu_roots[1].name[0]=0;
}
int main(){round2_usb_direction_labels();round1_network_and_rom_metadata();compact_rom_selection();native_file_size_rows();easyflash_disabled_ui();preferences_title_case_values();power_confirmations();network_safe_entry();autostart_value_alignment();hardware_separator_roles();submenu_group_rules();separator_hierarchy_colors();usability_label_widths();borders();markers();ordinary_values();scroll();cleanup_layouts();final_corrections();
 assert(FG_COLOR==E64_MENU_TEXT && HILITE_COLOR==E64_MENU_HIGHLIGHT && BORDER_COLOR==E64_MENU_BORDER);
 assert(E64_TITLE_TEXT_COLOR==E64_MENU_HEADER && E64_BANNER_TEXT_COLOR==E64_MENU_FOOTER);
}
'''
main=main.replace('@PREF_VALUES@',','.join(json.dumps(v) for v in pref_values))
# Keep these Power-test dependencies out of the shared capture harness.
power_test_main = 'static int menu_width_chars=40,menu_height_chars=25;\nstatic int calc_root_menu_left(){return 0;}\nstatic int calc_root_menu_top(){return 0;}\nstatic void ui_clear_menu(int n){memset(&menu_roots[n],0,sizeof(menu_roots[n]));}\n' + function('ui_push_menu') + '\n' + main
with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='menu-theme-test-') as tmp:
 tmp=Path(tmp);(tmp/'theme-under-test.h').write_text(THEME);source=tmp/'test.cpp';source.write_text(pre+functions+power_test_main);exe=tmp/'test'
 # Legacy TEXTFIELD branch in unchanged ui_action compares int with strlen.
 cmd=['c++','-std=c++11','-Wall','-Wextra','-Werror','-Wno-sign-compare','-I'+str(ROOT/'third_party/common'),str(source),'-o',str(exe)]
 subprocess.run(cmd,check=True);subprocess.run([str(exe)],check=True)
 # Role edits propagate through the actual renderer aliases and frame calls.
 (tmp/'theme-under-test.h').write_text(THEME.replace('#define E64_MENU_BORDER 14','#define E64_MENU_BORDER 6').replace('#define E64_MENU_TEXT 1\n','#define E64_MENU_TEXT 13\n').replace('#define E64_MENU_HIGHLIGHT 3','#define E64_MENU_HIGHLIGHT 10').replace('#define E64_MENU_INTERNAL_SEPARATOR 11','#define E64_MENU_INTERNAL_SEPARATOR 15'))
 subprocess.run(cmd,check=True);subprocess.run([str(exe)],check=True)
# When the privately staged stock CHARGEN is available, audit the exact
# pixels at every corner/edge join without embedding or altering ROM bytes.
rom_path=ROOT/'build/e64-install-review/c64/chargen'
if rom_path.exists():
 rom=rom_path.read_bytes()
 def glyph(code):return rom[code*8:code*8+8]
 h=glyph(0x40);v=glyph(0x5d)
 for tl,tr,bl,br in [(0x55,0x49,0x4a,0x4b),(0x70,0x6e,0x6d,0x7d)]:
  for left,right in [(tl,tr),(bl,br)]:
   assert all(bool(glyph(left)[y]&1)==bool(h[y]&128) for y in range(8))
   assert all(bool(glyph(right)[y]&128)==bool(h[y]&1) for y in range(8))
  assert glyph(tl)[7]==glyph(tr)[7]==v[0]
  assert glyph(bl)[0]==glyph(br)[0]==v[7]
 for code in [0x6b,0x73]:
  assert glyph(code)[0]==v[7] and glyph(code)[7]==v[0]
 # Authentic downward/upward T junctions share the horizontal stroke and
 # connect to the unchanged vertical on the adjacent character row.
 for code,edge in [(0x72,7),(0x71,0)]:
  assert glyph(code)[edge]==v[0]
  for y in range(8):
   assert bool(glyph(code)[y]&128)==bool(h[y]&128)
   assert bool(glyph(code)[y]&1)==bool(h[y]&1)
assert 'fixed_bottom + E64_MENU_HELP_RESERVED_ROWS' in UI
print('PASS: production theme roles and propagation, rounded/square inner/outer glyphs, borders/joins, selection markers/alignment, first/last scrolling, expanded/collapsed folders, protected header/footer space; disk internal spacing and immediate RETURN/navigation/reopening; popup longest-label/marker/arrow sizing, unchanged left padding and one extra right cell, centering, bounded highlight, long-label guards and exclusions; two theme variants.')
