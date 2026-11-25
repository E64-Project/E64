#!/usr/bin/env python3
"""Execute the production Power menu and confirmations without hardware I/O."""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'third_party/common/menu_power.c').read_text()
source = re.sub(r'^#include .*$', '', source, flags=re.M)
harness = r'''
#include <assert.h>
#include <string.h>
enum { MENU_SOFT_RESET, MENU_HARD_RESET, MENU_POWER_REBOOT,
       MENU_POWER_OFF, MENU_CONFIRM_CANCEL };
struct menu_item { int id; char name[36]; const char *label; void (*on_value_changed)(struct menu_item *); };
static struct menu_item nodes[32], dialog;
static int count, events[16], event_count, selected;
static struct menu_item *add(int id, const char *label) {
  struct menu_item *p=&nodes[count++]; p->id=id; p->label=label;
  p->on_value_changed=0; return p;
}
static struct menu_item *ui_menu_add_folder(struct menu_item *p,const char *s) {
  (void)p; return add(-1,s);
}
static struct menu_item *ui_menu_add_button(int id,struct menu_item *p,const char *s) {
  (void)p; return add(id,s);
}
static struct menu_item *ui_push_menu(int w,int h) {
  assert(w==16 && h==6); count=0; return &dialog;
}
static void ui_menu_add_read_only_heading(struct menu_item *p,const char *s) {(void)p;add(-2,s);}
static void ui_menu_add_divider(struct menu_item *p) {(void)p;add(-3,"");}
static void ui_select_first_interactive_item(void) {selected++;}
static void emux_detach_disk(int n) {events[event_count++]=n;}
static void emux_detach_tape(void) {events[event_count++]=12;}
static void menu_configs_before_reboot(void) {events[event_count++]=13;}
static void circle_reboot(void) {events[event_count++]=14;}
static void circle_power_off(void) {events[event_count++]=15;}
'''
checks = r'''
int main(void) {
  struct menu_item root={0}; build_power_menu(&root);
  assert(count==5 && !strcmp(nodes[0].label,"Power"));
  const char *labels[]={"Reboot","Shutdown","Immediate Soft Reset","Immediate Hard Reset"};
  const int ids[]={MENU_POWER_REBOOT,MENU_POWER_OFF,MENU_SOFT_RESET,MENU_HARD_RESET};
  for(int i=0;i<4;i++){assert(!strcmp(nodes[i+1].label,labels[i]));assert(nodes[i+1].id==ids[i]);}
  assert(!nodes[3].on_value_changed && !nodes[4].on_value_changed);
  void (*reboot)(struct menu_item *)=nodes[1].on_value_changed;
  void (*shutdown)(struct menu_item *)=nodes[2].on_value_changed;
  for(int off=0;off<2;off++) {
    event_count=0; (off?shutdown:reboot)(0);
    assert(!event_count && count==4&&!strcmp(dialog.name,"E64 Power Confirm"));
    assert(!strcmp(nodes[0].label,off?"SHUTDOWN":"REBOOT"));
    assert(nodes[1].id==-3);
    assert(!strcmp(nodes[2].label,off?"Shutdown Now":"Reboot Now"));
    assert(nodes[2].id==(off?MENU_POWER_OFF:MENU_POWER_REBOOT));
    assert(nodes[3].id==MENU_CONFIRM_CANCEL && !strcmp(nodes[3].label,"Cancel"));
    assert(!nodes[3].on_value_changed);
    nodes[2].on_value_changed(&nodes[2]);
    assert(event_count==(off?6:7));
    for(int i=0;i<5;i++)assert(events[i]==8+i);
    if(off)assert(events[5]==15);
    else assert(events[5]==13 && events[6]==14);
  }
  assert(selected==2); return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='e64-power-test-') as d:
    c = Path(d)/'power.c'; exe=Path(d)/'power-test'
    c.write_text(harness+source+checks)
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('PASS: Power order, labels, reset IDs, confirmation geometry/buttons, callbacks and shutdown/reboot sequencing')
