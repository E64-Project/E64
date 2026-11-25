#!/usr/bin/env python3
"""Test the production RAM recorder/renderer against a mocked firmware API."""
from pathlib import Path
import subprocess, tempfile
root = Path(__file__).resolve().parents[2]
header = r'''
#include <stdint.h>
typedef unsigned DISPMANX_RESOURCE_HANDLE_T;
typedef unsigned DISPMANX_ELEMENT_HANDLE_T;
typedef unsigned DISPMANX_DISPLAY_HANDLE_T;
typedef unsigned DISPMANX_UPDATE_HANDLE_T;
struct DISPMANX_MODEINFO_T { unsigned width,height; };
struct VC_RECT_T { int x,y,w,h; };
struct VC_DISPMANX_ALPHA_T { unsigned flags,opacity,mask; };
enum { VC_IMAGE_RGB565, DISPMANX_FLAGS_ALPHA_FIXED_ALL_PIXELS,
 DISPMANX_PROTECTION_NONE, DISPMANX_NO_ROTATE };
static int writes,adds,removes,raises; static bool available=true;
static void bcm_host_init() {}
static unsigned vc_dispmanx_display_open(int) {return available ? 1:0;}
static int vc_dispmanx_display_get_info(unsigned,DISPMANX_MODEINFO_T *i) {i->width=720;i->height=480;return 0;}
static unsigned vc_dispmanx_resource_create(int,int,int,uint32_t*) {return 2;}
static void vc_dispmanx_rect_set(VC_RECT_T *r,int x,int y,int w,int h) {*r={x,y,w,h};}
static int vc_dispmanx_resource_write_data(unsigned,int,int,void*,VC_RECT_T*) {writes++;return 0;}
static unsigned vc_dispmanx_update_start(int) {return 3;}
static int vc_dispmanx_update_submit(unsigned,void*,void*) {return 0;}
static unsigned vc_dispmanx_element_add(unsigned,unsigned,int,VC_RECT_T*,unsigned,VC_RECT_T*,int,VC_DISPMANX_ALPHA_T*,int,int) {adds++;return 4;}
static int vc_dispmanx_element_change_layer(unsigned,unsigned,int layer) {if(layer<0) removes++;else raises++;return 0;}
'''
test = r'''
#define E64_DIAG_HOST_TEST 1
#include "src/startup_diagnostic.cpp"
#include <cassert>
extern "C" { char font8x8_basic[256][8]; }
int main() {
 memset(font8x8_basic,0,sizeof font8x8_basic);
 memset(font8x8_basic['E'],0x80,8);
 e64_diag(1,"1 GPIO OK");e64_diag(2,"2 Recovery key: SHIFT+C=");
 assert(writes==0);assert(!strcmp(rows[1],"1 GPIO OK"));
 available=false;e64_diag_video();assert(writes==0);
 assert(strstr(rows[15],"unavailable"));available=true;
 e64_diag_video();assert(writes>0 && adds==1);
 assert(strstr(rows[2],"SHIFT+C="));assert(pixels[12*640+12]==0xffff && pixels[12*640+13]==0);
 e64_diag(14,"ERROR: SD mount failed");assert(strstr(rows[14],"SD mount"));
 char large[300];memset(large,'X',299);large[299]=0;
 e64_diag(6,"%s",large);assert(strlen(rows[6])==76);
 // Another core already drawing must never cause a spin or wait.
 drawing=1;int before=writes;e64_diag(5,"5 selected id");
 assert(writes==before && !strcmp(rows[5],"5 selected id"));drawing=0;
 e64_diag(9,"9 VICE init");assert(writes==before+1);
 e64_diag_first_frame();assert(removes==0);
 failed=false;
 e64_diag_first_frame();assert(removes==0);
 e64_diag(10,"10 CPU loop");e64_diag_first_frame();assert(removes==1);
 before=writes;e64_diag_first_frame();e64_diag(12,"USB complete");
 assert(removes==1 && writes==before);
 e64_diag(14,"ERROR: late USB failure");assert(raises==1 && writes==before+1);
 e64_diag_first_frame();assert(removes==1);
 return 0;
}
'''
with tempfile.TemporaryDirectory(dir=root/'build',prefix='diagnostic-test-') as tmp:
 p=Path(tmp);(p/'bcm_host.h').write_text(header);(p/'test.cpp').write_text(test)
 subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(p),'-I'+str(root),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,timeout=10)
print('PASS: production early RAM retention, unavailable display, replay, text rendering, error output, truncation, nonblocking contention and first-frame retirement')
