#include "webui.h"
#if BMC64_WEBUI && defined(E64_USB_INIT_DIAGNOSTICS)
#include "webui_usb_diag.h"
#include "webui_http.h"
#include <circle/usbinitdiag.h>

static const char *usb_diag_name(unsigned kind){
 static const char*const names[]={"UNKNOWN","HOST_BEGIN","HOST_RESULT","HUB_BEGIN","HUB_PORT","HUB_DEVICE_INIT","HUB_DEVICE_CONFIG","HUB_END","MASS_BEGIN","MASS_STAGE","CBW","DATA","CSW_LENGTH","CSW_STATUS","SCSI_RESULT","MASS_END","REGISTERED","DISK_INIT","MOUNT","DISCOVERY","CONTROLLER_REQUEST","CONTROLLER_RESULT","ALLOC_FAILURE","COMMAND_RESULT","DWHCI_COMPLETE"};
 return kind<sizeof(names)/sizeof(names[0])?names[kind]:"UNKNOWN";
}
void WebUiUsbInitDiagnostics(CSocket *socket){
 UsbInitDiagStatus s;usb_init_diag_status(&s);
 webhttp::CChunkedResponse response(socket,200,"OK","text/plain; charset=utf-8");
 response.Write("firmware=" USB_INIT_DIAG_ID "\nformat=1\nbaseline_sha256=e19f49aeb06c3d27b5403bd3deead837d9baf0259b3abde96c6d5fae7e4a08ee\nRAM only; diagnostic observer, not a USB fix\n");
 response.Printf("capacity=%u reserved=%u published=%u pending=%u full_dropped=%u contention_dropped=%u overflowed=%u\n",s.capacity,s.reserved,s.published,s.reserved-s.published,s.full_dropped,s.contention_dropped,s.overflowed);
 response.Write("order=reservation sequence; ticks=32-bit microsecond clock (may wrap)\nunit=USB address except DISK_INIT physical slot, MOUNT USB index 0..2, DISCOVERY/HOST=0\nfields: CBW/DATA/CSW_LENGTH a=requested b=reported_signed c=tag_or_direction d=opcode\nCSW_STATUS a=status b=residue c=tag d=signature\nSCSI_RESULT a=opcode b=result_signed c=expected_bytes d=0\nCONTROLLER_REQUEST a=bytes b=endpoint c=direction_in d=endpoint_type\nDWHCI_COMPLETE a=stage_status_bits b=HCTSIZ c=direction_in d=stage_result_length\nCONTROLLER_RESULT a=submitted b=URB_status c=length_signed d=USB_error(-1=not_applicable)\nMASS_END a=stage b=success c=registration_number d=blocks\nDISK_INIT a=presence b=DSTATUS; MOUNT a=0 b=FRESULT\nseq ticks core event unit a_hex b_signed b_hex c_hex d_hex\n");
 for(unsigned i=0;i<s.published&&!response.Failed();i++){
  UsbInitDiagEvent e;if(!usb_init_diag_read(i,&e))break;
  response.Printf("%u %u %u %s %u 0x%08x %d 0x%08x 0x%08x 0x%08x\n",e.sequence,e.ticks,e.core,usb_diag_name(e.kind),e.unit,e.a,(int32_t)e.b,e.b,e.c,e.d);
 }
 response.Finish();
}
#endif
