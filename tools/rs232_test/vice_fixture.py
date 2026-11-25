# Actual rsuser.c with VICE platform/alarm boundaries mocked, real public headers.
v=root/'third_party/vice-3.3/src'
header('vice.h','#define HAVE_RS232BMC')
header('alarm.h','''#include <stdint.h>
typedef uint32_t CLOCK;
typedef struct alarm_s {CLOCK next;int active;} alarm_t;
static alarm_t alarm_instance;
static inline alarm_t*alarm_new(void*a,const char*b,void(*f)(CLOCK,void*),void*d){return &alarm_instance;}
static inline void alarm_set(alarm_t*a,CLOCK c){a->next=c;a->active=1;}
static inline void alarm_unset(alarm_t*a){a->active=0;}
''')
header('clkguard.h','static inline void clk_guard_add_callback(void*a,void(*f)(CLOCK,void*),void*b){}')
header('maincpu.h','static CLOCK maincpu_clk;\nstatic void *maincpu_alarm_context,*maincpu_clk_guard;')
header('machine.h','enum {VICE_MACHINE_C64=1,VICE_MACHINE_VIC20=2};\nstatic int machine_class=VICE_MACHINE_C64;')
header('log.h','#define LOG_DEFAULT 0\n#define log_error(...) ((void)0)')
source=Path(__file__).with_name('vice_test.c').read_text().replace('RSUSER_SOURCE',str(v/'rs232drv/rsuser.c'))
(t/'vice_test.c').write_text(source)
exe=t/'vice'
run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-variable','-Wno-sign-compare','-fsanitize=undefined','-I'+str(t),'-I'+str(v),t/'vice_test.c','-o',exe]);run([exe])
