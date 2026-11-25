#!/usr/bin/env python3
"""Exercise the production footer renderer with captured CHARGEN draw calls."""
from pathlib import Path
import re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
ui=(ROOT/'third_party/common/ui.c').read_text()
match=re.search(r'^static void ui_draw_menu_footer\([^;]*?\)\s*\{',ui,re.M)
assert match
function=ui[match.start():ui.index('\n}',match.end())+2]
color='#include "'+str(ROOT/'third_party/common/menu_theme.h')+'"'
code=r'''
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
COLOR
static const void *raw_video_font=(void*)1;
struct Draw {std::string text; int x,y,color,glyph;};
static std::vector<Draw> draws;
static int ui_text_width(const char *text){return strlen(text)*8;}
static void ui_draw_c64_upper_text(const char *text,int x,int y,int color){
 if(raw_video_font)draws.push_back({text,x,y,color,-1});
}
static void ui_draw_char_raw(int glyph,int x,int y,int color,void *buffer,int pitch,int scale){
 assert(!buffer && pitch==0 && scale==1);
 draws.push_back({"",x,y,color,glyph});
}
FUNCTION
int main(){
 int widths[]={264,272,280,288,320,384,480,640};
 int offsets[]={0,16,37};
 for(int width:widths)for(int left:offsets){
  draws.clear();ui_draw_menu_footer(left,211,width);
  assert(draws.size()==4);
  auto nav=draws[0],center=draws[1],arrow=draws[2],exit=draws[3];
  assert(nav.text=="CRSR NAV" && nav.x==left+4);
  assert(center.text=="ENTER SELECT");
  assert(center.x==left+(width-ui_text_width("ENTER SELECT"))/2);
  assert(arrow.glyph==0x1f && arrow.text.empty());
  assert(exit.text==" EXIT" && exit.x==arrow.x+8);
  int left_margin=nav.x-left;
  int right_margin=left+width-(exit.x+ui_text_width(exit.text.c_str()));
  assert(left_margin==right_margin && left_margin==4);
  // Frame edge at left-8 / right+8: same one-cell margins as header.
  assert(nav.x-(left-8)==12);
  assert(left+width+8-(exit.x+ui_text_width(exit.text.c_str()))==12);
  assert(nav.x+ui_text_width(nav.text.c_str())+8<=center.x);
  assert(center.x+ui_text_width(center.text.c_str())+8<=arrow.x);
  for(auto draw:draws){assert(draw.y==211 && draw.color==8);}
 }
 // Small panels retain only the full-width centered section, without overlap.
 for(int width:{96,104,112,120,144,192,232,247}){
  draws.clear();ui_draw_menu_footer(24,19,width);
  assert(draws.size()==1 && draws[0].text=="ENTER SELECT");
  assert(draws[0].x==24+(width-96)/2 && draws[0].y==19);
 }
 for(int width:{0,64,88,95}){
  draws.clear();ui_draw_menu_footer(24,19,width);assert(draws.empty());
 }
 // No font substitution if the genuine CHARGEN font is unavailable.
 raw_video_font=nullptr;draws.clear();ui_draw_menu_footer(16,32,320);
 assert(draws.empty());
}
'''.replace('COLOR',color).replace('FUNCTION',function)
with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='menu-footer-test-') as tmp:
 tmp=Path(tmp);source=tmp/'test.cpp';source.write_text(code);exe=tmp/'test'
 subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
assert 'ui_draw_menu_footer(left, top + height - 8, width);' in ui
print('PASS: production footer at 8 widths and 3 offsets; full-width centering, symmetrical 4px content insets, CHARGEN arrow $1F, orange color, fixed row, non-overlap, narrow-panel guards and no fallback font.')
