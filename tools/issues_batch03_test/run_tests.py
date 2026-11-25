#!/usr/bin/env python3
"""Host execution of production Batch 3 builders and native CHARGEN renderer."""
from pathlib import Path
import re, subprocess, tempfile
r=Path(__file__).resolve().parents[2]
ns={'__file__':str(r/'tools/menu_theme_test/run_tests.py')}
s=Path(ns['__file__']).read_text();exec(s[:s.index('with tempfile.TemporaryDirectory')],ns)
ui=(r/'third_party/common/ui.c').read_text();menu=(r/'third_party/common/menu.c').read_text();cfg=(r/'third_party/common/menu_configs.c').read_text()
def fn(s,n):
 m=re.search(r'^(?:static )?[\w *]+\b'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 return s[m.start():s.index('\n}',m.end())+2]
pre=ns['pre'].replace('#include <cassert>','#include <cassert>\n#include <cstdarg>')
missing=['MENU_WIFI_CONNECT_NOW','MENU_WIFI_PSK','MENU_SUB_CHANGE_VOLUME','MENU_VOLUME_SD','MENU_VOLUME_USB1','MENU_VOLUME_USB2','MENU_VOLUME_USB3','MENU_ERROR_DIALOG']
# Reuse IDs already present in the renderer's generated enum.
missing=[n for n in missing if not re.search(r'\b'+n+r'\b',','.join(ns['ids']))]
pre+='\nenum { '+','.join(n+'='+str(80000+i) for i,n in enumerate(missing))+' };\n'
helpers=ns['power_test_main'][:ns['power_test_main'].index(ns['main'])]+r'''
static menu_item pool[256];static int used;
static menu_item *add(menu_item*p,const char*s,int id,menu_item_type type){auto*n=&pool[used++];assert(used<256);memset(n,0,sizeof(*n));n->type=type;n->id=id;strcpy(n->name,s);n->menu_top=p->menu_top;n->menu_left=p->menu_left;n->menu_width=p->menu_width;n->menu_height=p->menu_height;auto**tail=&p->first_child;while(*tail)tail=&(*tail)->next;*tail=n;return n;}
menu_item *ui_menu_add_button(int id,menu_item*p,const char*s){auto*n=add(p,s,id,BUTTON);strcpy(n->displayed_value," ");return n;}
menu_item *ui_menu_add_read_only(menu_item*p,const char*s,menu_item_type type){auto*n=add(p,s,-1,type);n->disabled=1;return n;}
menu_item *ui_menu_add_read_only_heading(menu_item*p,const char*s){return ui_menu_add_read_only(p,s,READ_ONLY_HEADING);}
menu_item *ui_menu_add_divider(menu_item*p){return add(p,"",-1,DIVIDER);}
menu_item *ui_menu_add_text_field_limit(int id,menu_item*p,char*s,char*value,int limit){auto*n=add(p,s,id,TEXTFIELD);strcpy(n->str_value,value);n->max_length=limit;return n;}
static int usb_mask;
static void circle_find_usb(int (*a)[3]){for(int i=0;i<3;i++)(*a)[i]=(usb_mask>>i)&1;}
static char wifi_psk[64];static menu_item *wifi_psk_item;
void ui_render_single_frame(){}
static int ui_fb_h=240,ui_transparent_layer;volatile int ui_enabled=1;
void ui_enable_osd(){}
void glob_osd_popped(menu_item*,menu_item*){}
static void delete_confirmed(menu_item*){}
static void delete_first_yes(menu_item*){}
#define DIALOG_LINE_CHARS 28
'''
helpers+='\n'+fn(cfg,'push_menu')+'\n'+fn(cfg,'ready')+'\n'+fn(cfg,'delete_question')
helpers+='\n'+fn(ui,'ui_push_selection_popup')+'\n'+fn(menu,'filesystem_change_volume')+'\n'+fn(menu,'show_wifi_connect_dialog')
for n in ['add_dialog_lines','ui_push_dialog_header','ui_fit_message_dialog','ui_error']:helpers+='\n'+fn(ui,n)
main=ns['main'][:ns['main'].index('static void borders()')]+r'''
static void reset(int w,int h){used=0;current_menu=0;memset(menu_roots,0,sizeof(menu_roots));menu_roots[0].menu_width=w;menu_roots[0].menu_height=h;menu_roots[0].menu_top=(ui_fb_h-h)/2;menu_window_top[1]=0;root_section_boundary_count=0;}
static void draw(){clear_draws();ui_traverse();auto*r=&menu_roots[1];ui_draw_c64_panel(r->menu_left-8,r->menu_top-8,r->menu_width+16,r->menu_height+16,0);int idx=0;ui_render_children(r->first_child,1,&idx,0);for(auto it=texts.begin();it!=texts.end();)if(it->text.find_first_not_of(" ")==std::string::npos)it=texts.erase(it);else ++it;for(auto t:texts)if(!t.text.empty()){assert(t.x>=r->menu_left&&t.x+ui_text_width(t.text.c_str())<=r->menu_left+r->menu_width);assert(t.y>=r->menu_top&&t.y+8<=r->menu_top+r->menu_height);}for(auto g:glyphs)assert(g.code==E64_MENU_HORIZONTAL||g.code==E64_MENU_VERTICAL||g.code==E64_MENU_ROUND_TL||g.code==E64_MENU_ROUND_TR||g.code==E64_MENU_ROUND_BL||g.code==E64_MENU_ROUND_BR);}
int main(){
 for(int displayHeight:{240,247,272})for(int width:{320,336,384})for(int height:{192,200,224}){
 ui_fb_h=displayHeight;
 reset(width,height);ui_error("Fan: OFF must be below ON");auto*r=&menu_roots[1];assert(r->menu_width==240&&r->menu_height==48&&abs(2*r->menu_top+48-ui_fb_h)<=1);draw();int rules=0;for(auto g:glyphs)if(g.y==r->menu_top+16&&g.code==0x40){assert(g.color==E64_MENU_SEPARATOR&&g.code==0x40);rules++;}assert(rules==28);assert(texts[0].text=="Error"&&texts.back().text=="Fan: OFF must be below ON");
 reset(width,height);ui_error("Unrelated error");assert(!menu_roots[1].name[0]);draw();for(auto g:glyphs)if(g.y==menu_roots[1].menu_top+8&&g.code==0x40)assert(g.color==E64_MENU_INTERNAL_SEPARATOR);
 for(usb_mask=0;usb_mask<8;usb_mask++){
 reset(width,height);menu_item source{};source.id=999;filesystem_change_volume(&source);r=&menu_roots[1];int count=1+__builtin_popcount((unsigned)usb_mask);assert(r->menu_height==48&&r->menu_top==(ui_fb_h-80)/2+16);
 int oldwidth=7*8;assert(r->menu_width==oldwidth-8&&r->menu_left==(width-oldwidth)/2);
 ui_select_first_interactive_item();for(int selected=0;selected<count;selected++){menu_cursor[1]=selected;draw();assert((int)texts.size()==count);for(int j=0;j<count;j++){auto t=texts[j];assert(t.y>=r->menu_top+8&&t.y+8<=r->menu_top+48-8);assert(t.y==r->menu_top-16+((80-count*8)/2/8)*8+j*8);}assert(rects.back().color==HILITE_COLOR);assert(menu_cursor_item[1]->sub_id==MENU_SUB_CHANGE_VOLUME);}
 int expected[]={MENU_VOLUME_SD,MENU_VOLUME_USB1,MENU_VOLUME_USB2,MENU_VOLUME_USB3};int n=0;for(auto*p=r->first_child;p;p=p->next){assert(p->id==999);int slot=0;if(n){for(int i=0,k=0;i<3;i++)if(usb_mask&(1<<i)){if(++k==n){slot=i+1;break;}}}assert(p->value==expected[slot]);n++;}assert(n==count);
 }
 for(int set:{0,1}){reset(width,height);strcpy(wifi_psk,set?"secret":"");show_wifi_connect_dialog();draw();r=&menu_roots[1];int statusY=-1,inputY=-1,saveY=-1;for(auto t:texts){if(t.text==(set?"Password Already Set":"Password Not Set"))statusY=t.y;if(t.text=="New Password: ")inputY=t.y;if(t.text=="Save & Reboot")saveY=t.y;}assert(statusY==r->menu_top+32&&inputY==r->menu_top+56&&saveY==inputY+8);assert(menu_cursor[1]==6&&wifi_psk_item->max_length==63);bool frame=false;for(auto g:glyphs)if(g.code==E64_MENU_ROUND_TL&&g.x==r->menu_left+8){assert(g.y==statusY-8);frame=true;}assert(frame);ui_action(ACTION_Down);assert(menu_cursor[1]==7);ui_action(ACTION_Up);assert(menu_cursor[1]==6);}
 for(int second:{0,1})for(const char*name:{"A","12345678901234567890123456789012"}){reset(width,height);delete_question("test-id",name,second,0);r=&menu_roots[1];int rows=0;menu_item*last=nullptr;for(auto*p=r->first_child;p;p=p->next){rows++;last=p;}assert(r->menu_height==(rows+2)*8&&r->menu_height<80);draw();assert(texts[0].text=="Delete Config"&&texts[0].color==E64_MENU_DISCONNECTED);assert(texts.back().y+8==r->menu_top+r->menu_height-8);assert(last->on_value_changed==(second?delete_confirmed:delete_first_yes)&&!strcmp(last->str_value,"test-id"));for(auto t:texts)if(t.text!="Delete Config")assert(t.color!=E64_MENU_DISCONNECTED);assert(menu_cursor_item[1]->id==MENU_CONFIRM_CANCEL);ui_action(ACTION_Down);ui_traverse();assert(menu_cursor_item[1]->id==MENU_CONFIGS_DELETE_CONFIRM);}
 }
}
'''
with tempfile.TemporaryDirectory(prefix='e64-batch03-') as d:
 p=Path(d);(p/'theme-under-test.h').write_text(ns['THEME']);(p/'test.cpp').write_text(pre+ns['functions']+helpers+main)
 subprocess.run(['g++','-std=c++17','-Wno-write-strings','-fsanitize=undefined','-I'+str(r/'third_party/common'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: Batch 3 production builders/rendering; 27 display/menu size combinations; fan centering/brown/unchanged other errors; all 8 USB combinations and choices; fixed Wi-Fi status frame and shifted controls/navigation; both Delete confirmations and max names, red heading, bottom clearance, callbacks, CHARGEN corners, text bounds.')
