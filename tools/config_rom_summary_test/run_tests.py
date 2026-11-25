#!/usr/bin/env python3
"""Execute Config ROM rows with production builders, renderer and navigation."""
from pathlib import Path
import re, subprocess, tempfile
r=Path(__file__).resolve().parents[2]
ns={'__file__':str(r/'tools/menu_theme_test/run_tests.py')}
src=Path(ns['__file__']).read_text();exec(src[:src.index('with tempfile.TemporaryDirectory')],ns)
ui=(r/'third_party/common/ui.c').read_text(); menu=(r/'third_party/common/menu_configs.c').read_text();api=(r/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
def fn(s,n):
 m=re.search(r'^(?:static )?[\w *]+\b'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 return s[m.start():s.index('\n}',m.end())+2]
extra='\n'.join(fn(ui,n) for n in ['append','ui_new_item','ui_menu_add_folder','ui_menu_add_read_only','ui_menu_add_read_only_heading','ui_collapse_folders','ui_expanded_branch'])
extra+='\n'+fn(api,'emux_config_rom_name')+'\n'+fn(api,'emux_get_string_1')+'\n#define CONFIG_ROM_VALUE_COLS 25\n'+'\n'.join(fn(menu,n) for n in ['config_rom_row_render','config_rom_summary_render','config_rom_summary_changed','add_config_rom_summary'])
pre=ns['pre']+r'''
enum StringSetting {Setting_ConfigROM,Setting_FSDeviceNDir};
static void resources_get_string_sprintf(const char*,const char**,int){assert(false);}
static const char *choices[3]={"kernal","basic","chargen"};
static int resources_get_string(const char *key,const char **out){const char*keys[]={"KernalName","BasicName","ChargenName"};for(int i=0;i<3;i++)if(!strcmp(key,keys[i])){*out=choices[i];return 0;}return -1;}
'''
main=r'''
static void frame(){texts.clear();glyphs.clear();rects.clear();ui_traverse();int i=0;ui_render_children(menu_roots[0].first_child,0,&i,0);}
int main(){
 auto *root=&menu_roots[0];root->type=FOLDER;root->is_expanded=1;root->menu_left=16;root->menu_top=24;root->menu_width=320;root->menu_height=200;
 auto *config=ui_menu_add_folder(root,(char*)"Config");config->is_expanded=1;add_config_rom_summary(config);auto*f=config->first_child;auto*a=f->first_child;auto*b=a->next;auto*c=b->next;
 assert(!f->is_expanded&&!strcmp(f->name,"ROMs in this Config >"));assert(a->disabled&&b->disabled&&c->disabled&&!c->next);
 menu_window_bottom[0]=20;ui_select_first_interactive_item();menu_cursor[0]=1;ui_traverse();assert(menu_cursor_item[0]==f);
 ui_action(ACTION_Return);frame();assert(f->is_expanded&&menu_cursor_item[0]==f);assert(!strcmp(a->name,"KERNAL  : Default")&&!strcmp(b->name,"BASIC   : Default")&&!strcmp(c->name,"CHARGEN : Default"));
 choices[0]="JiffyDOS.bin";frame();assert(!strcmp(a->name,"KERNAL  : JiffyDOS.bin"));
 choices[1]="basic-custom.bin";choices[2]="/roms/chargen-custom.bin";frame();assert(!strcmp(b->name,"BASIC   : basic-custom.bin"));assert(!strcmp(c->name,"CHARGEN : chargen-custom.bin"));
 // Simulated Config load replaces resources, not active emulator ROM bytes.
 choices[0]="second.bin";choices[1]="basic";choices[2]="chargen";frame();assert(!strcmp(a->name,"KERNAL  : second.bin")&&!strcmp(b->name,"BASIC   : Default"));
 choices[0]="kernal";frame();assert(!strcmp(a->name,"KERNAL  : Default"));choices[0]="/custom/kernal";frame();assert(!strcmp(a->name,"KERNAL  : kernal"));
 std::string longname;for(int i=0;i<255;i++)longname+=char('a'+i%26);choices[0]=longname.c_str();test_ticks=0;frame();
 for(unsigned offset=0;offset<=230;offset++){test_ticks=(offset+3)*1000000UL;frame();assert(strlen(a->name)==35);assert(std::string(a->name+10)==longname.substr(offset,25));for(auto t:texts)assert(t.x+int(t.text.size())*8<=root->menu_left+312);}
 // RETURN preserves focus, and each opening restarts the complete filename.
 for(int n=0;n<50;n++){ui_action(ACTION_Return);frame();assert(!f->is_expanded&&menu_cursor_item[0]==f);ui_action(ACTION_Return);frame();assert(f->is_expanded&&menu_cursor_item[0]==f);assert(std::string(a->name+10)==longname.substr(0,25));}
 assert(ui_expanded_branch(root->first_child,f,nullptr)==f); // C64 up-arrow target.
 f->is_expanded=0;ui_collapse_folders(f->first_child);frame();assert(!strcmp(f->name,"ROMs in this Config >")&&menu_cursor_item[0]==f);
 ui_action(ACTION_Return);frame();assert(f->is_expanded);
 ui_collapse_folders(root->first_child);ui_select_first_interactive_item();frame();assert(!config->is_expanded&&!f->is_expanded&&menu_cursor_item[0]==config); // HOME.
 config->is_expanded=1;frame();assert(!strcmp(f->name,"ROMs in this Config >"));
 puts("PASS: defaults, custom choices, configuration resource replacement, immediate selection/default refresh, 255-byte complete filename, bounded native render, 100 RETURN toggles and stable focus");
}
'''
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'theme-under-test.h').write_text(ns['THEME']);(p/'test.cpp').write_text(pre+'\n'+ns['functions']+'\n'+extra+'\n'+main)
 subprocess.run(['g++','-std=c++17','-Wno-write-strings','-I'+str(r/'third_party/common'),'-I'+str(p),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
assert menu.index('add_config_rom_summary(parent);')>menu.index('"Select An Existing Config >"')
assert 'if (node->on_render) node->on_render(node);' in ui
