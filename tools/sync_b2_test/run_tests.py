#!/usr/bin/env python3
"""Complete production CDevice/CPartition classes and headers, with host platform support."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2];circle=root/'third_party/circle-stdlib/libs/circle'
with tempfile.TemporaryDirectory(prefix='e64-sync-b2-') as name:
 t=Path(name);(t/'circle').mkdir()
 (t/'assert.h').write_text('#include \"/usr/include/assert.h\"\n')
 (t/'circle/types.h').write_text('#pragma once\n#include <cstdint>\n#include <cstddef>\nusing u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;using s32=int32_t;using uintptr=uintptr_t;using boolean=bool;\n#define TRUE true\n#define FALSE false\n')
 (t/'circle/string.h').write_text('#pragma once\n#include <string>\nclass CString{std::string s;public:CString&operator=(const char*p){s=p;return *this;}operator const char*()const{return s.c_str();}void TrimRight(){while(!s.empty()&&s.back()==32)s.pop_back();}};\n')
 exe=t/'test'
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=undefined','-pthread','-I'+str(t),'-I'+str(circle/'include'),str(Path(__file__).with_name('test.cpp')),str(circle/'lib/device.cpp'),str(circle/'lib/fs/partition.cpp'),str(circle/'lib/ptrlist.cpp'),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=30)
print('PASS: B2 whole production classes, actual headers and list implementation; no real storage accessed')
