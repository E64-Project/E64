#ifndef E64_USB_INIT_DIAG_H
#define E64_USB_INIT_DIAG_H
/* Temporary RAM-only observer. No USB/filesystem actions or output in hooks. */
#ifdef E64_USB_INIT_DIAGNOSTICS
#include <stdint.h>
#define USB_INIT_DIAG_CAPACITY 2048U
#define USB_INIT_DIAG_ID "E64 Stage 2A USB Diagnostic D1"
#ifdef __cplusplus
extern "C" {
#endif
enum {
 UDI_HOST_BEGIN=1, UDI_HOST_RESULT, UDI_HUB_BEGIN, UDI_HUB_PORT,
 UDI_HUB_DEVICE_INIT, UDI_HUB_DEVICE_CONFIG, UDI_HUB_END,
 UDI_MASS_BEGIN, UDI_MASS_STAGE, UDI_CBW, UDI_DATA, UDI_CSW_LENGTH,
 UDI_CSW_STATUS, UDI_SCSI_RESULT, UDI_MASS_END, UDI_REGISTERED,
 UDI_DISK_INIT, UDI_MOUNT, UDI_DISCOVERY, UDI_CONTROLLER_REQUEST,
 UDI_CONTROLLER_RESULT, UDI_ALLOC_FAILURE, UDI_COMMAND_RESULT, UDI_DWHCI_COMPLETE
};
typedef struct {
 uint32_t sequence,ticks,core,kind,unit,a,b,c,d;
} UsbInitDiagEvent;
typedef struct {
 uint32_t capacity,reserved,published,full_dropped,contention_dropped,overflowed;
} UsbInitDiagStatus;
void usb_init_diag_record(uint32_t kind,uint32_t unit,uint32_t a,uint32_t b,uint32_t c,uint32_t d);
void usb_init_diag_status(UsbInitDiagStatus *out);
int usb_init_diag_read(uint32_t index,UsbInitDiagEvent *out);
void usb_init_diag_mass_begin(uint32_t address);
void usb_init_diag_mass_end(uint32_t address);
int usb_init_diag_interested(uint32_t address);
/* Evaluate and return the original result exactly once. */
int usb_init_diag_result(uint32_t kind,uint32_t unit,uint32_t a,uint32_t c,uint32_t d,int result);
#ifdef __cplusplus
}
class UsbInitDiagMassScope {
 uint32_t address,stage,ok,number,blocks;
public:
 explicit UsbInitDiagMassScope(uint32_t id,uint32_t endpoints):address(id),stage(1),ok(0),number(0),blocks(0){
  usb_init_diag_mass_begin(address);usb_init_diag_record(UDI_MASS_BEGIN,address,endpoints,0,0,0);
 }
 void Stage(uint32_t value){stage=value;usb_init_diag_record(UDI_MASS_STAGE,address,stage,0,0,0);}
 void Success(uint32_t n,uint32_t b){ok=1;number=n;blocks=b;}
 ~UsbInitDiagMassScope(){usb_init_diag_record(UDI_MASS_END,address,stage,ok,number,blocks);usb_init_diag_mass_end(address);}
};
#endif
#endif
#endif
