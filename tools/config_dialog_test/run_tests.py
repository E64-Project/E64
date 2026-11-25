#!/usr/bin/env python3
"""Execute native Config builders/rendering/editing with a deterministic clock.
Optional private stock ROM: --chargen /path/to/chargen (never written).
"""
from pathlib import Path
import re,subprocess,tempfile,argparse
r=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--chargen',type=Path,default=r/'build/e64-install-review/c64/chargen');args=p.parse_args()
# Share existing native renderer dependencies and capture backend, not test results.
ns={'__file__':str(r/'tools/menu_theme_test/run_tests.py')}
theme_source=Path(ns['__file__']).read_text();exec(theme_source[:theme_source.index('with tempfile.TemporaryDirectory')],ns)
ui=(r/'third_party/common/ui.c').read_text();menus=(r/'third_party/common/menu_configs.c').read_text()
def fn(source,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',source,re.M);assert m,name
 return source[m.start():source.index('\n}',m.end())+2]
assert 'if (key == KEYCODE_Delete) { ui_delete_forward(); return; }' in fn(ui,'ui_key_pressed')
assert ui.index('ui_text_cursor_reset();',ui.index('struct menu_item *ui_pop_menu('))<ui.index('ui_clear_menu(current_menu);',ui.index('struct menu_item *ui_pop_menu('))
assert 'memset(ui_fb, BG_COLOR, ui_fb_h * ui_fb_pitch);' in fn(ui,'ui_render_single_frame')
pre=ns['pre'].replace('#include <cstring>','#include <cstring>\n#include <cstdlib>\n#include <climits>').replace('#define BMC64_NEW_KEYBOARD_INPUT 0','#define BMC64_NEW_KEYBOARD_INPUT 1').replace('menu_item *ui_pop_menu(){--current_menu;return &menu_roots[current_menu];}','')
# Pixel backend uses unmodified ROM bytes when available. No glyphs are generated.
pre=pre.replace('static void ui_draw_char_raw(int c,int x,int y,int color,void*,int,int){glyphs.push_back({c,x,y,color});}',r'''
static unsigned char screen[384][512],rom[4096];static bool have_rom;
static void draw_rom(int code,int bank,int x,int y,int color){
 if(!have_rom)return;
 for(int row=0;row<8;row++)for(int col=0;col<8;col++)if(rom[bank+8*(code&255)+row]&(128>>col))if(x+col>=0&&x+col<512&&y+row>=0&&y+row<384)screen[y+row][x+col]=color;
}
static void ui_draw_char_raw(int c,int x,int y,int color,void*,int,int){glyphs.push_back({c,x,y,color});draw_rom(c,0,x,y,color);}
''')
pre=pre.replace('void ui_draw_rect(int x,int y,int w,int h,int color,int fill){rects.push_back({x,y,w,h,color,fill});}',r'''void ui_draw_rect(int x,int y,int w,int h,int color,int fill){rects.push_back({x,y,w,h,color,fill});for(int row=y;row<y+h;row++)for(int col=x;col<x+w;col++)if(row>=0&&row<384&&col>=0&&col<512)screen[row][col]=color;}''')
pre=pre.replace('void ui_draw_text(const char *s,int x,int y,int color){texts.push_back({s,x,y,color});}',r'''void ui_draw_text(const char *s,int x,int y,int color){texts.push_back({s,x,y,color});for(const unsigned char *p=(const unsigned char*)s;*p;p++,x+=8){int code=*p,bank=0;if(code>='A'&&code<='Z')code=code-'A'+1;else if(code>='a'&&code<='z'){code=code-'a'+1;bank=0x800;}draw_rom(code,bank,x,y,color);}}''')
extra=fn(ui,'ui_clear_child_menu')+'\n'+fn(ui,'ui_clear_menu')+'\n'+fn(ui,'ui_pop_menu')+'\n'+fn(ui,'append')+'\n'+fn(ui,'ui_new_item')+'\n'+fn(ui,'ui_menu_add_text_field_limit')+'\n'+fn(ui,'ui_delete_forward')+'\n'+fn(ui,'ui_type_char')
helpers=r'''
void ui_find_first(char){assert(false);}
static unsigned long new_config_timing;
static std::string saved;static int commits;
static void name_entered(menu_item *item){saved=item->str_value;commits++;ui_pop_menu();}
static void ready(){ui_select_first_interactive_item();}
menu_item *ui_push_menu(int w,int h){ui_text_cursor_reset();current_menu++;assert(current_menu<NUM_MENU_ROOTS);auto*root=&menu_roots[current_menu];memset(root,0,sizeof(*root));root->type=FOLDER;root->menu_width=w*8;root->menu_height=h*8;root->menu_left=16+(320-root->menu_width)/2;root->menu_top=24+(200-root->menu_height)/2;menu_window_top[current_menu]=0;menu_window_bottom[current_menu]=h;menu_cursor[current_menu]=0;return root;}
menu_item *ui_menu_add_read_only_heading(menu_item *p,const char *text){auto*n=ui_new_item(p,text,-1);n->type=READ_ONLY_HEADING;n->disabled=1;append(p,n);return n;}
menu_item *ui_menu_add_divider(menu_item*p){auto*n=ui_new_item(p,"",-1);n->type=DIVIDER;append(p,n);return n;}
menu_item *ui_menu_add_button(int id,menu_item*p,const char*text){auto*n=ui_new_item(p,text,id);n->type=BUTTON;strcpy(n->displayed_value," ");append(p,n);return n;}
'''
# Actual production Config name builder, with only submit callback mocked.
helpers+='\n'+fn(menus,'show_name_dialog')
main=r'''
static void frame(){memset(screen,BG_COLOR,sizeof(screen));rects.clear();texts.clear();glyphs.clear();for(int n=0;n<=current_menu;n++){if(n==current_menu)ui_traverse();int index=0;ui_render_children(menu_roots[n].first_child,n,&index,0);}}
static int blocks(){int n=0;for(auto a:rects)if(a.color==E64_MENU_SELECTED_TEXT&&a.w==8&&a.h==8)n++;return n;}
static Rect block(){for(auto a:rects)if(a.color==E64_MENU_SELECTED_TEXT&&a.w==8&&a.h==8)return a;assert(false);return {};}
static menu_item *open(int id,const char *name){show_name_dialog(id,id==MENU_CONFIGS_NEW_NAME?"New Config Name":"Rename Config",name);frame();auto*f=menu_cursor_item[current_menu];assert(f&&f->type==TEXTFIELD&&f->max_length==32);assert(menu_cursor[current_menu]==2);return f;}
static void glyph_cell(Rect b,unsigned code,int bank,bool inverted){if(!have_rom)return;for(int y=0;y<8;y++)for(int x=0;x<8;x++){bool ink=rom[bank+8*code+y]&(128>>x);assert(screen[b.y+y][b.x+x]==(ink?(inverted?HILITE_COLOR:E64_MENU_SELECTED_TEXT):(inverted?E64_MENU_SELECTED_TEXT:HILITE_COLOR)));}}
int main(int argc,char**argv){
 if(argc>1){FILE*fp=fopen(argv[1],"rb");assert(fp);assert(fread(rom,1,sizeof(rom),fp)==sizeof(rom));fclose(fp);have_rom=true;for(int n=0;n<8;n++)assert(rom[0xa0*8+n]==255);}
 current_menu=0;menu_roots[0].type=FOLDER;menu_roots[0].menu_left=16;menu_roots[0].menu_top=24;menu_roots[0].menu_width=320;menu_roots[0].menu_height=200;ui_menu_add_button(999,&menu_roots[0],"Root Action");
 for(int id:{MENU_CONFIGS_NEW_NAME,MENU_CONFIGS_RENAME_NAME})for(const char*name:{"","Existing"}){
  int before=commits;auto*f=open(id,name);auto&root=menu_roots[1];assert(root.menu_width==288&&root.menu_height==40);assert(root.menu_top==24+(200-40)/2);auto*r=root.first_child;
  bool title=false,divider=false;for(auto t:texts)if(t.text==(id==MENU_CONFIGS_NEW_NAME?"New Config Name":"Rename Config")){title=true;assert(t.y==root.menu_top+4&&t.x==root.menu_left+(288-ui_text_width(t.text.c_str()))/2);}
  for(auto g:glyphs)if(g.code==E64_MENU_HORIZONTAL){divider=true;assert(g.y==root.menu_top+16);}assert(title&&divider&&r->next->type==DIVIDER);
  assert(blocks()==1);Rect b=block();assert(b.y==root.menu_top+28&&b.x==root.menu_left+12+(int)strlen(name)*8);assert(b.y+8==root.menu_top+36);assert(root.menu_height-(b.y+8-root.menu_top)==4);
  if(!*name)glyph_cell(b,0x20,0,true);
  std::string untouched=f->str_value;test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;frame();assert(blocks()==0&&untouched==f->str_value);test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;frame();assert(blocks()==1&&untouched==f->str_value);
  // Mid-name inversion preserves original glyph and restores normal pixels.
  strcpy(f->str_value,"ABC");f->value=1;frame();b=block();glyph_cell(b,2,0,true);test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;frame();assert(blocks()==0);glyph_cell(b,2,0,false);
  ui_action(ACTION_Right);frame();assert(block().x==b.x+8);ui_action(ACTION_Left);frame();assert(block().x==b.x);
  ui_type_char('X');frame();assert(!strcmp(f->str_value,"AXBC")&&f->value==2);ui_type_char('\b');frame();assert(!strcmp(f->str_value,"ABC")&&f->value==1);
  test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;frame();assert(blocks()==0);ui_delete_forward();frame();assert(!strcmp(f->str_value,"AC")&&f->value==1&&blocks()==1);
  f->value=0;ui_type_char('\b');assert(!strcmp(f->str_value,"AC"));ui_delete_forward();assert(!strcmp(f->str_value,"C"));
  strcpy(f->str_value,"A\xc3\xa9Z");f->value=3;frame();assert(block().x==root.menu_left+12+16);ui_action(ACTION_Left);assert(f->value==1);ui_action(ACTION_Right);assert(f->value==3);ui_type_char('\b');assert(!strcmp(f->str_value,"AZ")&&f->value==1);
  ui_type_char(0xe9);assert(!strcmp(f->str_value,"A\xc3\xa9Z")&&f->value==3);f->value=1;ui_delete_forward();assert(!strcmp(f->str_value,"AZ")&&f->value==1);
  memset(f->str_value,'M',32);f->str_value[32]=0;f->value=32;frame();b=block();assert(b.x==root.menu_left+12+32*8&&b.x+8==root.menu_left+276);ui_type_char('!');assert(strlen(f->str_value)==32&&f->value==32);
  // Cancel does not dispatch submit; clearing/redrawing leaves no field/cursor.
  ui_action(ACTION_Escape);assert(current_menu==0&&ui_text_cursor_field==nullptr&&commits==before);frame();assert(blocks()==0);for(int y=b.y;y<b.y+8;y++)for(int x=b.x;x<b.x+8;x++)assert(screen[y][x]==BG_COLOR);
  f=open(id,"Confirmed");for(int n=0;n<4;n++){test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;frame();assert(!strcmp(f->str_value,"Confirmed"));}ui_action(ACTION_Return);assert(saved=="Confirmed"&&commits==before+1&&current_menu==0);frame();assert(blocks()==0);
 }
 // Fast close/reopen, including identical allocations/empty strings, starts visible.
 for(int n=0;n<40;n++){open(MENU_CONFIGS_RENAME_NAME,"");assert(blocks()==1);test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;frame();assert(!blocks());ui_pop_menu();frame();assert(!blocks());}
 // Optional calibration Cancel stays within its original six-row frame.
 new_config_timing=1022736;auto*f=open(MENU_CONFIGS_NEW_NAME,"");assert(menu_roots[1].menu_height==48);frame();for(auto q:rects)assert(q.y+q.h<=menu_roots[1].menu_top+48);new_config_timing=0;ui_pop_menu();
 // Related Config lists align bars with the separator; marker/name spacing unchanged.
 for(int id:{MENU_CONFIGS_SELECT_ITEM,MENU_CONFIGS_DELETE_ITEM,MENU_CONFIGS_RENAME_NAME}){
  auto*root=ui_push_menu(38,12);root->is_submenu=1;strcpy(root->name,E64_MENU_CONFIG_LIST_TAG);ui_menu_add_read_only_heading(root,"Select Config");ui_menu_add_divider(root);auto*entry=ui_menu_add_button(id,root,"NTSC - Default");if(id==MENU_CONFIGS_SELECT_ITEM)ui_menu_mark_option(entry,1);menu_cursor[1]=2;frame();std::vector<Rect> bars;for(auto q:rects)if(q.y>=root->menu_top)bars.push_back(q);assert(bars.size()==1&&bars[0].color==HILITE_COLOR&&bars[0].x==root->menu_left+8&&bars[0].x+bars[0].w==root->menu_left+root->menu_width-8);for(auto g:glyphs)if(g.code==E64_MENU_HORIZONTAL)assert(g.color==E64_MENU_SUBMENU_SEPARATOR&&g.x>=bars[0].x&&g.x+8<=bars[0].x+bars[0].w);for(auto t:texts)if(t.text=="*")assert(t.x>=bars[0].x&&t.x+8<=bars[0].x+bars[0].w);ui_pop_menu();
 }
 // Common input rendering: masked/network/filename fields keep their layout/limits.
 for(int kind=0;kind<4;kind++){
  auto*root=ui_push_menu(38,10);f=ui_menu_add_text_field_limit(kind==1?MENU_NET_IP_ADDRESS:999,root,(char*)(kind==1?"IP Address":"Name"),(char*)(kind==0?"secret":kind==3?"":"filename"),20);f->textfield_masked=kind==0;f->textfield_right_aligned=kind==3;f->value=kind==3?0:2;frame();Rect b=block();std::string before=f->str_value;assert(b.x>=root->menu_left&&b.x+8<=root->menu_left+root->menu_width-8);if(kind==0){bool masked=false;for(auto t:texts){assert(t.text!="secret");masked|=t.text=="******";}assert(masked);}test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;frame();assert(!blocks()&&before==f->str_value);ui_pop_menu();
 }
 // A selected field behind another popup must not draw a second cursor.
 ui_clear_menu(0);ui_menu_add_text_field_limit(999,&menu_roots[0],(char*)"Name",(char*)"Background",20);menu_cursor[0]=0;frame();assert(blocks()==1);
 auto*overlay=ui_push_menu(20,4);ui_menu_add_button(999,overlay,"Focus");frame();assert(blocks()==0);ui_pop_menu();frame();assert(blocks()==1);
 // Blink uses unsigned elapsed ticks, including timer wrap.
 menu_item test{};strcpy(test.str_value,"X");ui_text_cursor_reset();test_ticks=ULONG_MAX-5;assert(ui_text_cursor_on(&test));test_ticks+=E64_MENU_TEXT_CURSOR_BLINK_US;assert(!ui_text_cursor_on(&test));ui_clear_menu(0);
}
'''
# All declarations precede production helpers; only the UI transport is mocked.
code=pre+ns['functions']+'\n'+extra+'\n'+helpers+'\n'+main
with tempfile.TemporaryDirectory(prefix='e64-config-dialog-') as directory:
 t=Path(directory);(t/'theme-under-test.h').write_text(ns['THEME']);(t/'test.cpp').write_text(code);exe=t/'test'
 subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-variable','-Wno-sign-compare','-Wno-write-strings','-Wno-misleading-indentation','-fsanitize=undefined','-I'+str(r/'third_party/common'),str(t/'test.cpp'),'-o',str(exe)],check=True)
 subprocess.run([str(exe)]+([str(args.chargen)] if args.chargen.is_file() else []),check=True)
print('PASS: production compact Config builders, balanced rows, centered titles, empty/existing/mid/max-length blinking reverse cursor, UTF-8 typing/Backspace/Delete/Left/Right, confirm/cancel, timer wrap, 40 reopen cycles, no artifacts, Config list separator alignment and generic/masked/network input preservation')
print('PASS: stock C64 CHARGEN reverse-space and underlying-glyph pixel checks' if args.chargen.is_file() else 'NOTE: private stock CHARGEN unavailable; pixel checks skipped, layout/editing checks passed')
