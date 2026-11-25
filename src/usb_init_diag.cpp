#include <circle/usbinitdiag.h>
#ifdef E64_USB_INIT_DIAGNOSTICS
#include <circle/timer.h>
#include <circle/multicore.h>

namespace {
struct Slot { UsbInitDiagEvent event; uint32_t published; };
static Slot slots[USB_INIT_DIAG_CAPACITY];
static uint32_t reserved,full_dropped,contention_dropped,overflowed;
static uint32_t interested[128];
}
extern "C" void usb_init_diag_record(uint32_t kind,uint32_t unit,uint32_t a,uint32_t b,uint32_t c,uint32_t d) {
 // A bounded reservation, never a spin/wait for another writer. Each slot is
 // immutable after release publication. A preempted writer cannot block IRQs.
 uint32_t index=__atomic_load_n(&reserved,__ATOMIC_RELAXED);
 for(unsigned attempt=0;attempt<8;attempt++) {
  if(index>=USB_INIT_DIAG_CAPACITY){
   __atomic_store_n(&overflowed,1U,__ATOMIC_RELAXED);
   __atomic_fetch_add(&full_dropped,1U,__ATOMIC_RELAXED);return;
  }
  if(__atomic_compare_exchange_n(&reserved,&index,index+1,false,__ATOMIC_RELAXED,__ATOMIC_RELAXED)){
   UsbInitDiagEvent &e=slots[index].event;
   e.sequence=index+1;e.ticks=CTimer::GetClockTicks();
#ifdef ARM_ALLOW_MULTI_CORE
   e.core=CMultiCoreSupport::ThisCore();
#else
   e.core=0;
#endif
   e.kind=kind;e.unit=unit;e.a=a;e.b=b;e.c=c;e.d=d;
   __atomic_store_n(&slots[index].published,index+1,__ATOMIC_RELEASE);return;
  }
 }
 __atomic_fetch_add(&contention_dropped,1U,__ATOMIC_RELAXED);
}
extern "C" void usb_init_diag_status(UsbInitDiagStatus *out){
 out->capacity=USB_INIT_DIAG_CAPACITY;
 out->reserved=__atomic_load_n(&reserved,__ATOMIC_ACQUIRE);
 out->published=0;
 while(out->published<out->reserved && __atomic_load_n(&slots[out->published].published,__ATOMIC_ACQUIRE)==out->published+1)out->published++;
 out->full_dropped=__atomic_load_n(&full_dropped,__ATOMIC_RELAXED);
 out->contention_dropped=__atomic_load_n(&contention_dropped,__ATOMIC_RELAXED);
 out->overflowed=__atomic_load_n(&overflowed,__ATOMIC_RELAXED);
}
extern "C" int usb_init_diag_read(uint32_t index,UsbInitDiagEvent *out){
 if(index>=USB_INIT_DIAG_CAPACITY || __atomic_load_n(&slots[index].published,__ATOMIC_ACQUIRE)!=index+1)return 0;
 *out=slots[index].event;return 1;
}
extern "C" void usb_init_diag_mass_begin(uint32_t address){if(address<128)__atomic_fetch_add(&interested[address],1U,__ATOMIC_RELEASE);}
extern "C" void usb_init_diag_mass_end(uint32_t address){if(address<128)__atomic_fetch_sub(&interested[address],1U,__ATOMIC_RELEASE);}
extern "C" int usb_init_diag_interested(uint32_t address){return address<128&&__atomic_load_n(&interested[address],__ATOMIC_ACQUIRE)!=0;}
extern "C" int usb_init_diag_result(uint32_t kind,uint32_t unit,uint32_t a,uint32_t c,uint32_t d,int result){
 if(kind==UDI_CSW_LENGTH&&!usb_init_diag_interested(unit))return result;
 usb_init_diag_record(kind,unit,a,(uint32_t)result,c,d);return result;
}
#endif
