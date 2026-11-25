#!/usr/bin/env python3
"""Execute production title rendering, connection query and Config label code."""
from pathlib import Path
import re, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
def function(path, name):
    source = (ROOT/path).read_text()
    match = re.search(r'^(?:extern "C" )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{', source, re.M)
    assert match, name
    return source[match.start():source.index('\n}', match.end())+2]
header=(ROOT/'third_party/common/circle.h').read_text()
ui=(ROOT/'third_party/common/ui.c').read_text()
colors='#include "'+str(ROOT/'third_party/common/menu_theme.h')+'"'
constants='\n'.join(line for line in header.splitlines() if line.startswith('#define CIRCLE_NETWORK_LINK_'))
code=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#define BMC64_NETWORK 1
CONFIG_DEFS
COLORS
CONSTANTS
enum TNetDeviceType { NetDeviceTypeEthernet, NetDeviceTypeWLAN };
struct CNetDevice {
 bool up=false;
 static CNetDevice *devices[2];
 static CNetDevice *GetNetDevice(TNetDeviceType type) { return devices[type]; }
 bool IsLinkUp() { return up; }
};
CNetDevice *CNetDevice::devices[2]={nullptr,nullptr};
static void *network_subsystem;
static long live_second_cycles, live_frame_cycles;
static long machine_get_cycles_per_second() {return live_second_cycles;}
static long machine_get_cycles_per_frame() {return live_frame_cycles;}
struct Draw { std::string text; int x,y,color,heading; };
static std::vector<Draw> draws;
struct Glyph {int code,x,y,color;};
static std::vector<Glyph> glyphs;
static const void *raw_video_font=(void*)1;
static void ui_draw_char_raw(int code,int x,int y,int color,void *buffer,int pitch,int scale){assert(!buffer&&!pitch&&scale==1);glyphs.push_back({code,x,y,color});}
static int ui_text_width(const char *text) { return strlen(text)*8; }
static void ui_draw_c64_menu_text(const char *text,int x,int y,int color,int heading) {
 draws.push_back({text,x,y,color,heading});
}
struct menu_item { char name[36]; };
static menu_item status,save;
static menu_item *status_item=&status,*save_item=&save;
struct Info { const char *name; };
static Info info;
static const Info *configs_running() { return &info; }
'''.replace('CONSTANTS',constants).replace('COLORS',colors).replace('CONFIG_DEFS','\n'.join(line for line in (ROOT/'src/configs/configs.h').read_text().splitlines() if line.startswith(('#define CONFIGS_MAX_NAME_LEN '))))
code+='\n'+function('src/vice_network.cpp','circle_get_network_connections')
code+='\n'+function('third_party/vice-3.3/src/arch/raspi/vice_api.c','emux_running_is_ntsc')
code+='\n'+function('third_party/common/ui.c','ui_draw_c64_header_sections')
code+='\n'+function('third_party/common/ui.c','ui_draw_root_title')
code+='\n'+function('third_party/common/menu_configs.c','update_name_labels')
code+=r'''
int main() {
 CNetDevice eth,wifi;
 CNetDevice::devices[0]=&eth; CNetDevice::devices[1]=&wifi;
 const char *labels[]={"NONE","ETH","Wi-Fi","W+E"};
 network_subsystem=&eth;
 // VICE PAL, NTSC, old NTSC and PAL-N live clock/frame combinations.
 long timings[][2]={{985248,19656},{1022727,17095},{1022727,16768},{1023440,20520}};
 for (auto &timing:timings) {
  live_second_cycles=timing[0]; live_frame_cycles=timing[1];
  bool ntsc=timing[1]<19000;
  assert(emux_running_is_ntsc()==ntsc);
  unsigned sequence[]={0,1,3,2,0,2,3,1,0};
  for (unsigned mask:sequence) for (int width:{192,256,320,384}) {
   eth.up=mask&1;wifi.up=mask&2;
   assert(circle_get_network_connections()==mask);
   draws.clear();ui_draw_root_title(16,24,width);
   assert(draws.size()==3);
   assert(draws[0].text==(ntsc?"NTSC":"PAL"));
   assert(draws[0].x==16+(48-ui_text_width(ntsc?"NTSC":"PAL"))/2 && draws[0].y==24 && draws[0].color==5);
   assert(draws[1].text=="E64");
   assert(draws[1].x==16+(width-24)/2);
   assert(draws[1].y==24 && draws[1].color==7 && draws[1].heading==0);
   assert(draws[2].text==labels[mask]);
   assert(draws[2].x==16+width-48+(48-ui_text_width(labels[mask]))/2);
   assert(draws[0].x-16==(ntsc?8:12));
   if(mask==2)assert(16+width-(draws[2].x+40)==4);
   assert(draws[0].x+ui_text_width(draws[0].text.c_str())+8<=draws[1].x);
   assert(draws[1].x+24+8<=draws[2].x);
   assert(draws[2].y==24 && draws[2].color==(mask?5:2) && draws[2].heading==0);
   glyphs.clear();ui_draw_c64_header_sections(16,24,width,BORDER_COLOR);
   assert(glyphs.size()==6);
   for(int i=0;i<2;i++){
    int x=i?16+width-48-8:16+48;
    assert(glyphs[3*i].code==0x72&&glyphs[3*i].x==x&&glyphs[3*i].y==16);
    assert(glyphs[3*i+1].code==0x5d&&glyphs[3*i+1].x==x&&glyphs[3*i+1].y==24);
    assert(glyphs[3*i+2].code==0x71&&glyphs[3*i+2].x==x&&glyphs[3*i+2].y==32);
    for(int j=0;j<3;j++)assert(glyphs[3*i+j].color==BORDER_COLOR);
   }
   assert(glyphs[0].x-16==16+width-(glyphs[3].x+8));

  }
 }
 live_second_cycles=live_frame_cycles=0;assert(!emux_running_is_ntsc());
 // A narrow target keeps the centered title and suppresses overlapping labels.
 eth.up=wifi.up=true;draws.clear();ui_draw_root_title(0,0,96);
 assert(draws.size()==1 && draws[0].text=="E64" && draws[0].x==36);
 glyphs.clear();ui_draw_c64_header_sections(0,0,96,BORDER_COLOR);assert(glyphs.empty());
 raw_video_font=nullptr;ui_draw_c64_header_sections(0,0,320,BORDER_COLOR);assert(glyphs.empty());raw_video_font=(void*)1;
 eth.up=wifi.up=true;network_subsystem=nullptr;
 assert(circle_get_network_connections()==0); // Network disabled/uninitialized.
 network_subsystem=&eth;CNetDevice::devices[0]=nullptr;
 assert(circle_get_network_connections()==2);
 CNetDevice::devices[1]=nullptr;assert(circle_get_network_connections()==0);
 info.name="Default NTSC";update_name_labels();assert(!strcmp(status.name,"Active Config: Default NTSC"));
 info.name="Default NTSC";update_name_labels();assert(!strcmp(status.name,"Active Config: Default NTSC"));
 info.name="Default PAL";update_name_labels();assert(!strcmp(status.name,"Active Config: Default PAL"));
 info.name="12345678901234567890123456789012";update_name_labels();
 assert(!strcmp(status.name,"12345678901234567890123456789012"));
 status_item=save_item=nullptr;update_name_labels();
}
'''
with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='menu-title-test-') as tmp:
    tmp=Path(tmp);source=tmp/'test.cpp';source.write_text(code);exe=tmp/'test'
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
menu=(ROOT/'third_party/common/menu.c').read_text()
assert 'ui_menu_add_read_only_heading(parent, "Network Status:")' in menu
assert 'root, "Network Status:"' not in menu
assert 'id, root, "", (char *)name, CONFIGS_MAX_NAME_LEN)' in (ROOT/'third_party/common/menu_configs.c').read_text()
theme=(ROOT/'third_party/common/menu_theme.h').read_text()
assert '#define E64_MENU_BORDER 14' in theme
assert '#define E64_MENU_SEPARATOR 9' in theme
assert '#define E64_MENU_FOOTER 8' in theme
assert 'status_item = ui_menu_add_folder(root, "Config")' in (ROOT/'third_party/common/menu_configs.c').read_text()
print('PASS: live VICE PAL/NTSC/old NTSC/PAL-N timing; four network labels/colors; reconnect transitions; exact six-cell status sections, 8px NTSC/12px PAL/4px Wi-Fi centering, authentic top/vertical/bottom junctions, full-width centered yellow title, non-overlap at four widths and narrow-target guards; expandable Config label, 32-byte limit and unchanged border/separator/footer colors.')
