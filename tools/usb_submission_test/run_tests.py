#!/usr/bin/env python3
"""Production ledger and unchanged production CUSBRequest, sanitized host execution."""
from pathlib import Path
import tempfile,subprocess,os
root=Path(__file__).resolve().parents[2];circle=root/'third_party/circle-stdlib/libs/circle'
with tempfile.TemporaryDirectory(prefix='e64-submission-') as name:
 t=Path(name);(t/'circle/usb').mkdir(parents=True)
 (t/'assert.h').write_text('#include "/usr/include/assert.h"\n')
 (t/'circle/types.h').write_text('#pragma once\n#include <cstdint>\n#include <cstddef>\nusing u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using u64=uint64_t;using s8=int8_t;using s16=int16_t;using s32=int32_t;using s64=int64_t;using uintptr=uintptr_t;using boolean=bool;\n#define TRUE true\n#define FALSE false\n')
 (t/'circle/macros.h').write_text('#pragma once\n#define PACKED __attribute__((packed))\n')
 (t/'circle/classallocator.h').write_text('#pragma once\n#define DECLARE_CLASS_ALLOCATOR\n#define IMPLEMENT_CLASS_ALLOCATOR(x)\n')
 (t/'circle/usb/usbendpoint.h').write_text('#pragma once\nenum TEndpointType{EndpointTypeControl,EndpointTypeBulk,EndpointTypeInterrupt,EndpointTypeIsochronous};class CUSBEndpoint{TEndpointType t;public:explicit CUSBEndpoint(TEndpointType v=EndpointTypeBulk):t(v){}TEndpointType GetType()const{return t;}};\n')
 exe=t/'test'
 subprocess.run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fno-omit-frame-pointer','-fsanitize=address,undefined','-pthread','-I'+str(t),'-I'+str(circle/'include'),'-DSUBMISSION_SOURCE="'+str(circle/'lib/usb/usbsubmission.cpp')+'"',str(Path(__file__).with_name('test.cpp')),str(circle/'lib/usb/usbrequest.cpp'),'-o',str(exe)],check=True)
 # The managed host preloads its own library; keep ASan checks enabled
 # while permitting that library to precede the dynamic sanitizer runtime.
 # LeakSanitizer cannot run under this host tracer; only its exit scan is off.
 env=dict(os.environ);env['ASAN_OPTIONS']=env.get('ASAN_OPTIONS','')+':verify_asan_link_order=0:detect_leaks=0'
 subprocess.run([str(exe)],check=True,timeout=60,env=env)
 # Verify that the host preload workaround did not disable address checking.
 probe=t/'asan-probe.cpp';probe.write_text('#include <cstdlib>\nint main(){char*p=(char*)malloc(16);free(p);*(volatile char*)p=42;return 0;}\n')
 probe_exe=t/'asan-probe'
 subprocess.run(['c++','-O0','-g','-fsanitize=address',str(probe),'-o',str(probe_exe)],check=True)
 negative=subprocess.run([str(probe_exe)],env=env,capture_output=True,text=True,timeout=15)
 assert negative.returncode!=0 and 'heap-use-after-free' in negative.stderr,negative.stderr
 print('PASS: sanitizer negative control detects deliberate heap-use-after-free with the same host options')

print('PASS: production submission code + production CUSBRequest, ASan/UBSan; no real devices accessed')
