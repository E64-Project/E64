#!/usr/bin/env python3
"""Capture production divider drawing and independently vary both class roles."""
from pathlib import Path
import subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
ns = {'__file__': str(ROOT/'tools/menu_theme_test/run_tests.py')}
s = Path(ns['__file__']).read_text()
exec(s[:s.index('with tempfile.TemporaryDirectory')], ns)
main = ns['main'][:ns['main'].index('static void borders()')] + r'''
int main(){
 (void)ui_action;(void)ui_traverse;(void)ui_draw_c64_frame_divider;(void)ui_draw_c64_panel;
 menu_item d;item(d,DIVIDER,"");
 for(int stack:{0,1,2})for(int depth:{0,1,3}){
  current_menu=stack;menu_roots[stack]=d;menu_roots[stack].first_child=&d;
  menu_cursor[stack]=1;menu_window_top[stack]=0;menu_window_bottom[stack]=18;
  root_section_boundary_count=0;
  clear_draws();int index=0;ui_render_children(&d,stack,&index,depth);
  auto baseline=glyphs;auto baseline_texts=texts;auto baseline_rects=rects;assert(baseline.size()==38);
  menu_roots[stack].is_submenu=1;
  clear_draws();index=0;ui_render_children(&d,stack,&index,depth);
  assert(index==1&&glyphs.size()==baseline.size()&&texts.size()==baseline_texts.size()&&rects.size()==baseline_rects.size());
  for(unsigned i=0;i<texts.size();i++){auto a=baseline_texts[i],b=texts[i];assert(a.text==b.text&&a.x==b.x&&a.y==b.y&&a.color==b.color);}
  for(unsigned i=0;i<rects.size();i++){auto a=baseline_rects[i],b=rects[i];assert(a.x==b.x&&a.y==b.y&&a.w==b.w&&a.h==b.h&&a.color==b.color&&a.fill==b.fill);}
  for(unsigned i=0;i<glyphs.size();i++){
   auto a=baseline[i],b=glyphs[i];
   assert(a.code==0x40&&b.code==a.code&&a.x==b.x&&a.y==b.y);
   assert(b.x==24+(int)i*8);
   assert(a.color==(stack?E64_MENU_INTERNAL_SEPARATOR:depth?E64_MENU_EXPANDABLE_SEPARATOR:E64_MENU_SEPARATOR));
   assert(b.color==(stack?(depth?E64_MENU_EXPANDABLE_SEPARATOR:E64_MENU_SUBMENU_SEPARATOR):a.color));
  }
 }
 // The existing ROM selection rule follows the submenu role; power stays independent.
 for(const char*name:{"E64 ROM Selection","E64 Power Confirm"}){
  current_menu=1;menu_roots[1]=d;menu_roots[1].first_child=&d;
  strcpy(menu_roots[1].name,name);menu_cursor[1]=1;
  clear_draws();int index=0;ui_render_children(&d,1,&index,0);
  assert(glyphs.size()==38);
  for(auto g:glyphs)assert(g.code==0x40&&g.color==(!strcmp(name,"E64 ROM Selection")?E64_MENU_SUBMENU_SEPARATOR:E64_MENU_SEPARATOR));
 }
 // Reusing a submenu slot for a dialog must reset classification.
 current_menu=0;menu_roots[1].is_submenu=1;
 assert(ui_push_menu(30,10)->is_submenu==0);
}
'''
# Use the same production push function and minimal host dependencies.
push = ns['power_test_main'][:ns['power_test_main'].index(ns['main'])]
ui = (ROOT/'third_party/common/ui.c').read_text()
configs = (ROOT/'third_party/common/menu_configs.c').read_text()
assert configs.count('root->is_submenu = 1;') == 5
assert configs.count('strcpy(root->name, E64_MENU_CONFIG_LIST_TAG);') == 4
for name in ['menu.c','menu_usb.c','menu_image_contents.c']:
 assert '->is_submenu = 1;' in (ROOT/'third_party/common'/name).read_text()
with tempfile.TemporaryDirectory(prefix='e64-separators-') as tmp:
 p=Path(tmp); (p/'test.cpp').write_text(ns['pre']+ns['functions']+push+main)
 for sub,expanded in [(9,11),(2,11),(9,15),(2,15)]:
  theme=ns['THEME'].replace('#define E64_MENU_SUBMENU_SEPARATOR 9',f'#define E64_MENU_SUBMENU_SEPARATOR {sub}').replace('#define E64_MENU_EXPANDABLE_SEPARATOR 11',f'#define E64_MENU_EXPANDABLE_SEPARATOR {expanded}')
  (p/'theme-under-test.h').write_text(theme)
  subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-Wno-sign-compare','-I'+str(ROOT/'third_party/common'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],check=True)
print('PASS: submenu brown, preserved expandable/dialog colors, four independent role variants, identical CHARGEN glyphs/coordinates/lengths, root unchanged, stack reuse reset.')
