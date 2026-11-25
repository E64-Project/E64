#!/usr/bin/env python3
"""Exercise both cancel-first native deletion questions from production code."""
from pathlib import Path
import re,subprocess,tempfile
r=Path(__file__).resolve().parents[2];s=(r/'third_party/common/menu_configs.c').read_text()
def fn(name):
 m=re.search(r'^static [\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m
 return s[m.start():s.index('\n}',m.end())+2]
code=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
#include <deque>
#include "ui.h"
#include "menu_theme.h"
#include "../../src/configs/configs_internal.h"
enum {MENU_CONFIRM_CANCEL=100,MENU_CONFIGS_DELETE_CONFIRM};
struct Page{std::deque<menu_item> items;menu_item root{};};
static std::vector<Page*> stack;
static int calls,legacy_calls,errors,infos,result=CONFIGS_OK;
static menu_item *push_menu(int w,int h,const char*){assert(w==38&&h==10);auto*p=new Page;stack.push_back(p);return &p->root;}
static menu_item *add(const char *name){auto*p=stack.back();p->items.emplace_back();auto*item=&p->items.back();memset(item,0,sizeof(*item));snprintf(item->name,sizeof(item->name),"%s",name);return item;}
menu_item *ui_menu_add_read_only_heading(menu_item*,const char *name){return add(name);}
menu_item *ui_menu_add_button(int id,menu_item*,const char *name){auto*p=add(name);p->id=id;p->type=BUTTON;return p;}
menu_item *ui_pop_menu(){assert(!stack.empty());delete stack.back();stack.pop_back();return stack.empty()?nullptr:&stack.back()->root;}
static void ready(){auto*p=stack.back();auto it=p->items.begin();while(it!=p->items.end()&&it->type!=BUTTON)++it;assert(it!=p->items.end()&&!strcmp(it->name,"No")&&it->id==MENU_CONFIRM_CANCEL);}
void ui_error(const char*,...){errors++;}void ui_info(const char*,...){infos++;}
extern "C" int configs_delete(const char*id){assert(!strcmp(id,"test"));calls++;return result;}
extern "C" int configs_purge_legacy(const char*id){assert(!strcmp(id,"test"));legacy_calls++;return result;}
extern "C" const char *configs_management_error(){return "fault";}
extern "C" int configs_deleted_count(){return 1;}
extern "C" const char *configs_deleted_id(unsigned){return "test";}
extern "C" const char *configs_deleted_name(unsigned){return "My Config";}
int config_file_read(const char*,ConfigFile *out){snprintf(out->info.name,sizeof(out->info.name),"My Config");return CONFIGS_OK;}
static void remove_empty_cleanup_control(){}
static void delete_question(const char*,const char*,int,int);
FUNCTIONS
static void yes(){menu_item item=stack.back()->items.back();assert(item.on_value_changed);item.on_value_changed(&item);}
static std::string question(){std::string out;for(auto&i:stack.back()->items)if(i.type==READ_ONLY_DESCRIPTION){if(!out.empty())out+=' ';out+=i.name;}return out;}
int main(){
 for(int cancel:{0,1}){
  delete_question("test","My Config",0,0);assert(question()=="Delete Config \"My Config\"?");
  if(cancel){yes();assert(stack.size()==1&&question()=="Confirm permanent deletion of \"My Config\"?");assert(!strcmp(stack.back()->items.back().name,"Yes, Delete"));}
  ui_pop_menu();assert(calls==0&&legacy_calls==0&&stack.empty());
 }
 // The list parent remains underneath both questions and closes only on success.
 stack.push_back(new Page);delete_question("test","My Config",0,0);yes();assert(calls==0);yes();assert(calls==1&&infos==1&&stack.empty());
 stack.push_back(new Page);delete_question("test","My Config",0,1);yes();yes();assert(legacy_calls==1&&stack.empty());
 stack.push_back(new Page);delete_question("test","My Config",0,0);yes();result=-1;yes();assert(errors==1&&stack.size()==2);while(!stack.empty())ui_pop_menu();
}
'''.replace('#include <vector>','#include <vector>\n#include <string>')
code=code.replace('FUNCTIONS','\n'.join(fn(n) for n in ['delete_confirmed','delete_first_yes','delete_question']))
with tempfile.TemporaryDirectory(prefix='e64-native-delete-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-I'+str(r/'third_party/common'),str(p/'test.cpp'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
print('PASS: production native exact two-stage questions, default No, first/second cancel, two Yes, explicit legacy cleanup and filesystem-error popup')
