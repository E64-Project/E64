#!/usr/bin/env python3
"""Production Web endpoint -> native quick action -> device assignments -> USB events."""
from pathlib import Path
import re,subprocess,tempfile
R=Path(__file__).resolve().parents[2]
menu=(R/'third_party/common/menu.c').read_text();ui=(R/'third_party/common/ui.c').read_text();web=(R/'src/webui/webui.cpp').read_text();joy=(R/'third_party/common/joy.c').read_text();circle=(R/'third_party/common/circle.h').read_text()
def fn(s,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]
pre=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include <initializer_list>
#define FALSE false
#define MAX_JOY_PORTS 4
#define MAX_USB_DEVICES 4
#define PENDING_EMU_JOY_TYPE_ABSOLUTE 1
#define Setting_Mouse 1
struct menu_item {int value,num_choices,choice_ints[10],choice_disabled[10];};
struct {int device,port,configuration;} joydevs[4];
static menu_item *port_1_menu_item,*port_2_menu_item,*port_3_menu_item,*port_4_menu_item;
static int joyswap,overlay_swap,pending_emu_quick_func,emulator_devices[4],mouse_enabled;
static int vkbd_enabled,event_port,event_device,event_value;
static void emux_set_joy_port_device(int port,int device){emulator_devices[port-1]=device;}
static void emux_set_int(int setting,int value){assert(setting==Setting_Mouse);mouse_enabled=value;}
static void overlay_joyswap_changed(int state){overlay_swap=state;}
static void emux_joy_interrupt(int,int port,int device,int value){event_port=port;event_device=device;event_value=value;}
struct CSocket {int status;};
static bool HasHeader(const char *request,const char*){return !strcmp(request,"authorized");}
static void SendText(CSocket*s,int status,const char*,const char*){s->status=status;}
static void SendResponse(CSocket*s,int status,const char*,const char*,const char*,unsigned){s->status=status;}
enum {LogNotice};
class CLogger {public:static CLogger *Get(){static CLogger c;return &c;}void Write(const char*,int,const char*,const char*){}};
#define WEBUI_LOG "webui"
'''
for name in ['BTN_ASSIGN_SWAP_PORTS','JOYDEV_NONE','JOYDEV_MOUSE','JOYDEV_MOUSE_MICROMYS','JOYDEV_USB_0','JOYDEV_USB_1','JOYDEV_USB_2','JOYDEV_USB_3']:
 pre+=re.search(r'^#define '+name+r' .*$',circle,re.M).group()+'\n'
pre+='\n'.join(re.findall(r'^#define WEBUI_QUICKFUNC_.*$',web,re.M))+'\n'
pre+='\n'.join(fn(menu,name) for name in ['is_mouse_device','validated_port_choice','set_need_mouse','set_joy_item_to_value','ui_set_joy_items','menu_swap_joysticks','menu_joysticks_reversed','menu_joystick_mapping','menu_joystick_status'])
pre+='\n'+fn(ui,'emu_quick_func_interrupt')+'\n'+fn(joy,'emu_set_joy_usb_interrupt')
a=web.index('  if (is_post &&\n      (strcmp(target, "/api/reset")');b=web.index('\n  if (is_get) {',a)
pre+='\nstatic void endpoint(CSocket *socket,const char *request="authorized"){bool is_post=true;const char*target="/api/joysticks/swap";'+web[a:b].replace('return FALSE;','return;')+'}\n'
a=menu.index('  case BTN_ASSIGN_SWAP_PORTS:',menu.index('void menu_quick_func('));b=menu.index('  case BTN_ASSIGN_VKBD_TOGGLE:',a)
pre+='static void process_quick(){switch(pending_emu_quick_func){'+menu[a:b]+'default:assert(false);}pending_emu_quick_func=0;}\n'
pre+=r'''
int main(){
 menu_item ports[4]={};menu_item **ptrs[]={&port_1_menu_item,&port_2_menu_item,&port_3_menu_item,&port_4_menu_item};
 const int devices[]={JOYDEV_USB_0,JOYDEV_USB_1,JOYDEV_USB_2,JOYDEV_USB_3,JOYDEV_MOUSE,JOYDEV_NONE};
 for(int i=0;i<4;i++){*ptrs[i]=&ports[i];ports[i].num_choices=6;for(int n=0;n<6;n++)ports[i].choice_ints[n]=devices[n];joydevs[i]={devices[i],i+1,100+i};}
 ui_set_joy_items();CSocket socket={};endpoint(&socket,"unauthorized");assert(socket.status==403&&!pending_emu_quick_func);
 for(int n=0;n<4;n++){
  int old=menu_joysticks_reversed();assert(old==n%2);
  endpoint(&socket);assert(socket.status==202&&pending_emu_quick_func==BTN_ASSIGN_SWAP_PORTS&&menu_joysticks_reversed()==old);
  process_quick();assert(menu_joysticks_reversed()==!old&&overlay_swap==!old);
  assert(!strcmp(menu_joystick_status(),!old?"Reverse":" Normal"));
  assert(!strcmp(menu_joystick_mapping(),!old?"1=2 / 2=1":"1=1 / 2=2"));
  for(int usb=0;usb<4;usb++){
   emu_set_joy_usb_interrupt(usb,0x10);int expected=usb<2?(!old?2-usb:1+usb):1+usb;
   assert(event_port==expected&&event_device==devices[usb]&&event_value==0x10);
   assert(joydevs[usb].configuration==100+usb); // physical input configuration untouched
  }
  assert(emulator_devices[0]==joydevs[0].device&&emulator_devices[1]==joydevs[1].device);
  assert(ports[0].choice_ints[ports[0].value]==joydevs[0].device&&ports[1].choice_ints[ports[1].value]==joydevs[1].device);
 }
 // Native change is exactly the state returned to Web polling/page reload.
 menu_swap_joysticks();assert(menu_joysticks_reversed()==1);menu_swap_joysticks();assert(menu_joysticks_reversed()==0);
 // Existing mouse handling remains in the common swap path.
 joydevs[0].device=JOYDEV_MOUSE;joydevs[1].device=JOYDEV_USB_0;ui_set_joy_items();menu_swap_joysticks();
 assert(emulator_devices[0]==JOYDEV_USB_0&&emulator_devices[1]==JOYDEV_MOUSE&&mouse_enabled);
 puts("PASS Web header/202, queued native swap, Normal/Reverse, native menu/overlay sync, actual USB event port routing, physical configurations unchanged, mouse behavior; no reset/filesystem symbols linked");
}
'''
assert '"\\\"joystick_swap\\\":%d' in web and 'menu_joysticks_reversed(), warp' in web
with tempfile.TemporaryDirectory(prefix='e64-web-swap-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(pre)
 subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-Wno-sign-compare',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
