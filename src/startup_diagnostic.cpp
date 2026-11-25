#include "startup_diagnostic.h"
#if E64_PHASE1_DIAGNOSTIC && (defined(__arm__) || defined(E64_DIAG_HOST_TEST))
#include "bcm_host.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
extern "C" {
#include "../third_party/common/font.h"
}
// Fixed RAM only; no stdio device, SD logging, allocation, sleeps or polling.
// Stage rows have one startup writer. Rendering is best effort and nonblocking
// when the other core is already submitting a diagnostic update.
static char rows[16][77];
static uint16_t pixels[640 * 288];
static DISPMANX_RESOURCE_HANDLE_T resource;
static DISPMANX_ELEMENT_HANDLE_T element;
static unsigned char drawing;
static bool retired;
static bool failed;
static void render(void) {
  if (!resource || __atomic_load_n(&retired, __ATOMIC_ACQUIRE) || __atomic_test_and_set(&drawing, __ATOMIC_ACQUIRE)) return;
  memset(pixels, 0, sizeof pixels);
  for (unsigned r=0;r<16;r++)
    for (unsigned c=0;c<76;c++)
      for (unsigned y=0;y<8;y++)
        for (unsigned x=0;x<8;x++)
          if ((unsigned char)font8x8_basic[(unsigned char)__atomic_load_n(&rows[r][c], __ATOMIC_RELAXED)][y] & (0x80u>>x))
            pixels[(12+r*16+y)*640+12+c*8+x]=0xffff;
  VC_RECT_T rect; vc_dispmanx_rect_set(&rect,0,0,640,288);
  vc_dispmanx_resource_write_data(resource,VC_IMAGE_RGB565,1280,pixels,&rect);
  __atomic_clear(&drawing, __ATOMIC_RELEASE);
}
extern "C" void e64_diag(int stage, const char *format, ...) {
  if (stage<0 || stage>15) return;
  if (stage >= 14) {
    __atomic_store_n(&failed,true,__ATOMIC_RELEASE);
    if (__atomic_exchange_n(&retired,false,__ATOMIC_ACQ_REL) && element) {
      DISPMANX_UPDATE_HANDLE_T update=vc_dispmanx_update_start(0);
      if (update) {
        vc_dispmanx_element_change_layer(update,element,1000);
        vc_dispmanx_update_submit(update,nullptr,nullptr);
      }
    }
  }
  va_list args; va_start(args,format);
  char text[77] = {};
  vsnprintf(text,sizeof text,format,args);
  va_end(args);
  for (unsigned c=0;c<77;c++) __atomic_store_n(&rows[stage][c],text[c],__ATOMIC_RELAXED);
  render();
}
extern "C" void e64_diag_video(void) {
  // Called after VCHIQ, before the ordinary EGL/framebuffer initialization.
  bcm_host_init();
  DISPMANX_DISPLAY_HANDLE_T display=vc_dispmanx_display_open(0);
  DISPMANX_MODEINFO_T info;
  if (!display || vc_dispmanx_display_get_info(display,&info)) {
    e64_diag(15,"ERROR: diagnostic display unavailable"); return;
  }
  uint32_t native;
  resource=vc_dispmanx_resource_create(VC_IMAGE_RGB565,640,288,&native);
  if (!resource) { e64_diag(15,"ERROR: diagnostic resource unavailable"); return; }
  e64_diag(0,"E64 PHASE 1 STARTUP - last status retained until first frame");
  VC_RECT_T src,dst;
  vc_dispmanx_rect_set(&src,0,0,640<<16,288<<16);
  vc_dispmanx_rect_set(&dst,info.width/20,info.height/20,info.width*9/10,info.height*9/10);
  VC_DISPMANX_ALPHA_T alpha={DISPMANX_FLAGS_ALPHA_FIXED_ALL_PIXELS,255,0};
  DISPMANX_UPDATE_HANDLE_T update=vc_dispmanx_update_start(0);
  if (!update) { e64_diag(15,"ERROR: diagnostic update unavailable"); return; }
  element=vc_dispmanx_element_add(update,display,1000,&dst,resource,&src,
      DISPMANX_PROTECTION_NONE,&alpha,0,DISPMANX_NO_ROTATE);
  vc_dispmanx_update_submit(update,nullptr,nullptr);
}
extern "C" void e64_diag_first_frame(void) {
  if (__atomic_load_n(&retired,__ATOMIC_ACQUIRE) ||
      __atomic_load_n(&failed,__ATOMIC_ACQUIRE) ||
      !__atomic_load_n(&rows[10][0],__ATOMIC_ACQUIRE)) return;
  // The main CPU loop has already reported 10; a completed frame proves output.
  e64_diag(10,"10 Emulator running: first frame presented");
  __atomic_store_n(&retired,true,__ATOMIC_RELEASE);
  if (element) {
    DISPMANX_UPDATE_HANDLE_T update=vc_dispmanx_update_start(0);
    if (update) {
      vc_dispmanx_element_change_layer(update,element,-1000);
      vc_dispmanx_update_submit(update,nullptr,nullptr);
    }
  }
}
#endif
