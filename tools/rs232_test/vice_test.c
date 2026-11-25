#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "RSUSER_SOURCE"

static int network_opens,network_closes,network_writes,network_reads;
static int physical_opens,physical_closes,physical_writes,physical_reads,baud_value;
static unsigned parity_value=0,data_bits_value=8,stop_bits_value=1;
static int framing_requests;
static unsigned selection_value,opened_selection;
static int selection_requests;
/* VICE fixture models preference publication only. USB discovery itself is
 * exercised against production code by usb_test.cpp, not simulated here. */
int e64_rs232_usb_select(unsigned selection){
 if(selection>E64_RS232_USB_AUTO)return -1;
 ++selection_requests;selection_value=selection;return 0;
}
void e64_rs232_usb_discovery(e64_rs232_usb_discovery_t *snapshot){
 if(snapshot)*snapshot=(e64_rs232_usb_discovery_t){selection_value,0,0,0};
}
static int received=-1,flags,network_result,physical_result;
static uint8_t physical_byte=0xa5;
static unsigned char sent[65536];
int rs232drv_open(int d){network_opens++;return 7;}
void rs232drv_close(int f){network_closes++;}
int rs232drv_putc(int f,uint8_t b){network_writes++;return 0;}
int rs232drv_getc(int f,uint8_t*b){network_reads++;if(network_result>0)*b=0xa5;return network_result;}
int e64_rs232_usb_open(unsigned a,unsigned b){physical_opens++;baud_value=b;opened_selection=selection_value=a;
 parity_value=0;data_bits_value=8;stop_bits_value=1;return 0;}
int e64_rs232_usb_open_configured(unsigned adapter,unsigned baud,
                                unsigned parity,unsigned data_bits,unsigned stop_bits){
 if(parity>2||(data_bits!=7&&data_bits!=8)||(stop_bits!=1&&stop_bits!=2))return -1;
 int result=e64_rs232_usb_open(adapter,baud);
 if(!result){parity_value=parity;data_bits_value=data_bits;stop_bits_value=stop_bits;}
 return result;
}
int e64_rs232_usb_set_framing(unsigned parity,unsigned data_bits,unsigned stop_bits){
 if(parity>2||(data_bits!=7&&data_bits!=8)||(stop_bits!=1&&stop_bits!=2))return -1;
 ++framing_requests;parity_value=parity;data_bits_value=data_bits;stop_bits_value=stop_bits;
 return 0;
}
void e64_rs232_usb_close(void){physical_closes++;}
int e64_rs232_usb_set_baud(unsigned b){baud_value=b;return 0;}
int e64_rs232_usb_put(uint8_t b){sent[physical_writes++]=b;return 0;}
int e64_rs232_usb_get(uint8_t*b){physical_reads++;if(physical_result>0)*b=physical_byte;return physical_result;
static uint8_t physical_byte=0xa5;}
int resources_register_int(const resource_int_t*r){assert(!strcmp(r[0].name,"RsUserFTDI")&&r[0].factory_value==0);return 0;}

static int default_ftdi = -1;
static int default_enabled = -1;
static int default_baud = -1;
static int default_calls = 0;

int resources_set_default_int(const char *name, int value)
{
    if (!strcmp(name, "RsUserFTDI"))
        default_ftdi = value;
    else if (!strcmp(name, "RsUserEnable"))
        default_enabled = value;
    else if (!strcmp(name, "RsUserBaud"))
        default_baud = value;
    else
        return -1;

    ++default_calls;
    return 0;
}
int cmdline_register_options(const cmdline_option_t*c){return 0;}
static void flag(void){flags++;}
static void rx(uint8_t b){received=b;}
static void frame(unsigned char b){
 maincpu_clk+=100000;
 rsuser_set_tx_bit(0);
 CLOCK start=clk_start_tx;
 for(int i=0;i<8;i++){
   maincpu_clk=start+(i+1)*bit_clk_ticks;
   rsuser_set_tx_bit((b>>i)&1);
 }
 maincpu_clk=start+9*bit_clk_ticks;rsuser_set_tx_bit(1);
 maincpu_clk=start+10*bit_clk_ticks;keepup_tx_buffer();
}
/* Independent UART oracle: explicitly emit start, LSB-first data, parity,
 * stops. Population count (not production parity_bit) defines parity. */
static int uart_bits(unsigned value,int bits,int parity,int stops,int *wave){
 unsigned mask=bits==7?0x7f:0xff,v=value&mask,ones=0;
 for(unsigned n=v;n;n&=n-1)++ones;
 int length=0;wave[length++]=0;
 for(int i=0;i<bits;++i)wave[length++]=!!(v&(1u<<i));
 if(parity)wave[length++]=parity==1?(ones%2):!(ones%2);
 for(int i=0;i<stops;++i)wave[length++]=1;
 return length;
}
/* Use true bit boundaries, not the production sampling clock as boundaries.
 * Return the next frame boundary, allowing consecutive frames with no gap. */
static CLOCK send_wave(CLOCK start,const int *wave,int length,int forwarded,unsigned expected){
 int before=physical_writes;
 for(int i=0;i<length;++i){
  maincpu_clk=start+i*bit_clk_ticks;rsuser_set_tx_bit(wave[i]);
  assert(physical_writes==before); /* No forwarding before last stop sample. */
 }
 maincpu_clk=start+length*bit_clk_ticks;keepup_tx_buffer();
 assert(physical_writes==before+forwarded);
 if(forwarded)assert(sent[before]==expected);
 assert(!clk_start_tx&&!clk_start_bit&&!clk_end_tx);
 return maincpu_clk;
}
static void waveform_regression(void){
 const unsigned values[]={0x00,0x01,0x55,0x7f,0x80,0xa5,0xff};
 const int rates[]={300,600,1200,2400};
 int netwrites=network_writes;
 for(int clock=0;clock<2;++clock)for(int rate=0;rate<4;++rate)
 for(int bits=7;bits<=8;++bits)for(int parity=0;parity<3;++parity)for(int stops=1;stops<=2;++stops){
  cycles_per_sec=clock?1022727:985248;
  assert(!set_baudrate(rates[rate],NULL));assert(!set_parity(parity,NULL));
  assert(!set_data_bits(bits,NULL));assert(!set_stop_bits(stops,NULL));
  rsuser_reset();physical_result=0;physical_writes=0;
  int wave[12],length=uart_bits(0,bits,parity,stops,wave);
  double ideal=(double)cycles_per_sec/rates[rate];
  assert(bit_clk_ticks<=ideal&&ideal-bit_clk_ticks<1.01);
  if(bits==8&&parity==0&&stops==1)
   assert(char_clk_ticks==(int)(10.0*cycles_per_sec/rates[rate]));
  else assert(char_clk_ticks==length*bit_clk_ticks);
  if(rates[rate]==2400&&bits==8&&parity==0&&stops==1){
   assert(bit_clk_ticks==(clock?426:410));
   assert(char_clk_ticks==(clock?4261:4105));
  }
  CLOCK next=maincpu_clk+100000;
  maincpu_clk=next;rsuser_set_tx_bit(1);maincpu_clk+=length*bit_clk_ticks;keepup_tx_buffer();
  assert(!physical_writes&&!clk_start_tx); /* Idle marks are not start bits. */
  next=maincpu_clk;
  for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);++i){
   length=uart_bits(values[i],bits,parity,stops,wave);
   next=send_wave(next,wave,length,1,values[i]&(bits==7?0x7f:0xff));
  }
  /* Wrong parity and each stop position, followed immediately by recovery.
   * Legacy 8N1 stop checking is already exercised by the inherited parser. */
  if(bits!=8||parity||stops!=1){
   for(int bad=-1;bad<stops;++bad){
    if(bad==-1&&!parity)continue;
    length=uart_bits(0xa5,bits,parity,stops,wave);
    int index=bad==-1?1+bits:length-stops+bad;wave[index]^=1;
    next=send_wave(next,wave,length,0,0);
    length=uart_bits(0x55,bits,parity,stops,wave);
    next=send_wave(next,wave,length,1,0x55);
   }
  }
  /* Alarm-driven continuous RX: sample near both edges of every bit cell.
   * No parity_bit(), frame_bits() or code[] is used for expected waveforms. */
  physical_byte=values[0];physical_result=1;maincpu_clk=next+100000;int_rsuser(0,NULL);
  for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);++i){
   CLOCK start=clk_start_rx;int oldflags=flags;
   assert(rxstate==1&&start==maincpu_clk);
   length=uart_bits(values[i],bits,parity,stops,wave);
   assert(alarm_instance.next==start+char_clk_ticks);
   for(int cell=0;cell<length;++cell)for(int edge=0;edge<2;++edge){
    maincpu_clk=start+cell*bit_clk_ticks+(edge?bit_clk_ticks-1:0);
    assert(rsuser_get_rx_bit()==wave[cell]);
   }
   maincpu_clk=start+char_clk_ticks-1;assert(rsuser_get_rx_bit()==1);
   if(i+1<sizeof(values)/sizeof(values[0]))physical_byte=values[i+1];else physical_result=0;
   maincpu_clk=alarm_instance.next;int_rsuser(0,NULL);
   unsigned v=values[i]&(bits==7?0x7f:0xff),reversed=0;
   for(int j=0;j<8;++j){reversed=reversed*2+(v%2);v/=2;}
   assert(received==(int)reversed);
   if(physical_result)assert(flags==oldflags+1&&rxstate==1&&clk_start_rx==maincpu_clk);
   else assert(flags==oldflags&&!rxstate&&!clk_start_rx&&rsuser_get_rx_bit()==1);
  }
  /* Start real partial TX/RX, change one field, then send a complete new frame. */
  for(int field=0;field<3;++field){
   physical_result=1;physical_byte=0xa5;maincpu_clk+=100000;int_rsuser(0,NULL);
   assert(rxstate==1);rsuser_set_tx_bit(0);maincpu_clk+=bit_clk_ticks;rsuser_set_tx_bit(1);
   assert(valid>0&&clk_start_tx);int written=physical_writes;
   int p=rsuser_parity,d=rsuser_data_bits,s=rsuser_stop_bits;
   int requests=framing_requests;CLOCK txclock=clk_start_tx,rxclock=clk_start_rx;unsigned samples=valid;
   assert(set_parity(3,NULL)==-1&&set_data_bits(6,NULL)==-1&&set_stop_bits(0,NULL)==-1);
   assert(framing_requests==requests&&clk_start_tx==txclock&&clk_start_rx==rxclock&&valid==samples);
   assert(rsuser_parity==p&&rsuser_data_bits==d&&rsuser_stop_bits==s);
   if(field==0)p=(p+1)%3;else if(field==1)d=d==7?8:7;else s=s==1?2:1;
   assert(!set_parity(p,NULL));assert(!set_data_bits(d,NULL));assert(!set_stop_bits(s,NULL));
   assert(parity_value==(unsigned)p&&data_bits_value==(unsigned)d&&stop_bits_value==(unsigned)s);
   assert(!valid&&!rxstate&&!clk_start_tx&&!clk_start_rx&&!clk_start_bit&&!clk_end_tx);
   assert(physical_writes==written);physical_result=0;
   length=uart_bits(0xa5,d,p,s,wave);
   send_wave(maincpu_clk+100000,wave,length,1,0xa5&(d==7?0x7f:0xff));
   physical_result=1;physical_byte=0xa5;maincpu_clk+=100000;int_rsuser(0,NULL);
   CLOCK fresh=clk_start_rx;assert(rxstate==1&&fresh==maincpu_clk);
   for(int cell=0;cell<length;++cell){
    maincpu_clk=fresh+cell*bit_clk_ticks+bit_clk_ticks/2;
    assert(rsuser_get_rx_bit()==wave[cell]);
   }
   physical_result=0;maincpu_clk=alarm_instance.next;int_rsuser(0,NULL);
   assert(!rxstate&&rsuser_get_rx_bit()==1);
  }
 }
 assert(network_writes==netwrites);
 assert(!set_parity(0,NULL));assert(!set_data_bits(8,NULL));assert(!set_stop_bits(1,NULL));
 physical_result=0;rsuser_reset();
}

/* CCGMS 2021 UP9600: initial idle SDR followed by
 * two encoded SDR fragments for one character.
 * Exercise production rsuser.c without enabling
 * high-speed physical FTDI baud rates.
 */
static void ccgms_up9600_idle_regression(void){
 assert(fd==RSUSER_FTDI_FD);
 assert(rsuser_data_bits==8);
 assert(rsuser_parity==0);
 assert(rsuser_stop_bits==1);

 unsigned before=physical_writes;

 buf=(unsigned int)~0u;
 valid=0;

 /* CCGMS initializes the serial output with $FF. */
 rsuser_tx_byte(0xff);
 assert(valid==8);

 /* Actual CCGMS UP9600 encoding, all 256 characters. */
 for(unsigned ch=0;ch<256;++ch){
  unsigned reversed=0;

  for(unsigned i=0;i<8;++i)
   reversed=(reversed<<1)|((ch>>i)&1u);

  rsuser_tx_byte((uint8_t)(reversed>>1));

  if(ch==0)
   assert(valid==9);

  rsuser_tx_byte((uint8_t)((ch&0x80u)|0x7fu));

  /* Each character must arrive exactly once. */
  assert(physical_writes==(int)(before+ch+1));
  assert(sent[before+ch]==(uint8_t)ch);
 }
}

/* CCGMS UP9600 receive-order characterization.
 * The next FLAG must not be raised in the same
 * callback that delivers the preceding SDR byte.
 * This test is expected to fail until scheduling
 * is corrected.
 */
static void ccgms_up9600_receive_order_regression(void){
 int before;

 assert(fd==RSUSER_FTDI_FD);

 physical_result=0;
 rsuser_reset();
 int saved_baud=rsuser_baudrate;
 /* Test high-speed scheduling without enabling
  * the unsupported production baud resource. */
 rsuser_baudrate=9600;
 calculate_baudrate();
 before=flags;

 physical_byte=0x55;
 physical_result=1;
 maincpu_clk+=100000;
 int_rsuser(0,NULL);

 assert(flags==before+1);
 assert(rxstate==1);

 /* Proposed UP9600 receive timing: SDR at nine bit
  * periods, next FLAG at the full character boundary.
  */
 CLOCK start=clk_start_rx;
 CLOCK sdr_due=start+9*bit_clk_ticks;
 CLOCK next_start=start+char_clk_ticks;

 assert(sdr_due<next_start);
 assert(alarm_instance.next==sdr_due);

 /* Second physical character is waiting. */
 physical_byte=0xaa;
 maincpu_clk=sdr_due;
 int_rsuser(0,NULL);

 /* SDR delivered, but next FLAG not yet generated. */
 assert(received==code[0x55]);
 assert(flags==before+1);
 assert(alarm_instance.next==next_start);

 /* Next FLAG occurs at the original character boundary. */
 maincpu_clk=next_start;
 int_rsuser(0,NULL);

 assert(flags==before+2);
 assert(rxstate==1);
 assert(clk_start_rx==next_start);

 physical_result=0;
 rsuser_baudrate=saved_baud;
 calculate_baudrate();
 rsuser_reset();
}

static void selection_regression(void){
 assert(!set_enable(0,NULL));assert(!set_baudrate(2400,NULL));
 assert(!set_parity(0,NULL));assert(!set_data_bits(8,NULL));assert(!set_stop_bits(1,NULL));
 for(int selection=1;selection<=E64_RS232_USB_AUTO;++selection){
  assert(!set_ftdi(selection,NULL));assert(rsuser_ftdi==selection);
  assert(selection_value==(unsigned)selection&&!rsuser_enabled);
  int net=network_opens,opens=physical_opens;
  assert(!set_enable(1,NULL));assert(physical_opens==opens+1&&network_opens==net);
  assert(opened_selection==(unsigned)selection&&fd==RSUSER_FTDI_FD);
  assert(baud_value==2400&&parity_value==0&&data_bits_value==8&&stop_bits_value==1);
  int requests=selection_requests;
  assert(set_ftdi(-1,NULL)==-1&&set_ftdi(18,NULL)==-1&&set_ftdi(100,NULL)==-1);
  assert(selection_requests==requests&&rsuser_ftdi==selection&&rsuser_enabled);
  if(selection==E64_RS232_USB_AUTO){
   assert(!set_enable(0,NULL));e64_rs232_usb_discovery_t snapshot;
   e64_rs232_usb_discovery(&snapshot);assert(snapshot.requested==E64_RS232_USB_AUTO&&!snapshot.ready&&!snapshot.resolved);
   assert(!set_enable(1,NULL));assert(opened_selection==E64_RS232_USB_AUTO&&network_opens==net);
   physical_result=0;int writes_before=network_writes;frame(0x55);
   assert(network_writes==writes_before); /* Absence never opens legacy backend. */
  }
  assert(!set_enable(0,NULL));
 }
 assert(!set_ftdi(0,NULL));int net=network_opens;
 assert(!set_enable(1,NULL));assert(network_opens==net+1&&fd==7&&selection_value==0);
}
int main(void){
 assert(rsuser_ftdi==0&&!rsuser_enabled&&rsuser_baudrate==300);
 assert(!rsuser_resources_init());
 assert(default_calls == 3);
 assert(default_ftdi == E64_RS232_USB_AUTO);
 assert(default_enabled == 1);
 assert(default_baud == 2400);
 rsuser_init(1000000,flag,rx);
 assert(!set_enable(1,NULL));assert(network_opens==1&&fd==7);
 buf=0;valid=5;assert(!set_ftdi(1,NULL));assert(valid==0);assert(physical_opens==1&&network_closes==1&&fd==RSUSER_FTDI_FD);
 assert(rsuser_parity==0&&rsuser_data_bits==8&&rsuser_stop_bits==1);
 assert(parity_value==0&&data_bits_value==8&&stop_bits_value==1&&!framing_requests);
 for(int clock=0;clock<2;clock++){
 cycles_per_sec=clock?1022727:985248;calculate_baudrate();
 const int rates[]={300,600,1200,2400};
 for(int rate=0;rate<4;rate++){
  assert(!set_baudrate(rates[rate],NULL));
  assert(baud_value==rates[rate]&&char_clk_ticks==(int)(10.0*cycles_per_sec/rates[rate]));
  assert(parity_value==0&&data_bits_value==8&&stop_bits_value==1);
  assert(bit_clk_ticks==char_clk_ticks/10);
  double ideal=(double)cycles_per_sec/rates[rate];
  assert((ideal-bit_clk_ticks)/ideal<0.0025);
  physical_writes=0;physical_result=0;
  for(int i=0;i<256;i++)frame(i);
  assert(physical_writes==256&&network_writes==0);
  for(int i=0;i<256;i++)assert(sent[i]==i);
  physical_result=-1;flags=0;int_rsuser(0,NULL);assert(flags==0&&rxstate==0);
  physical_byte=0;physical_result=1;int_rsuser(0,NULL);assert(flags==1&&rxstate==1);
  for(int i=0;i<256;i++){
   CLOCK start=clk_start_rx;
   for(int bit=0;bit<10;bit++){
    maincpu_clk=start+bit*bit_clk_ticks;
    rsuser_set_tx_bit(bit==0?0:bit==9?1:(i>>(bit-1))&1);
    maincpu_clk=start+bit*bit_clk_ticks+bit_clk_ticks/2;
    int want=bit==0?0:bit==9?1:(i>>(bit-1))&1;
    assert(rsuser_get_rx_bit()==want);
   }
   maincpu_clk=start+char_clk_ticks;
   keepup_tx_buffer();
   assert(physical_writes==257+i&&sent[256+i]==i);
   physical_byte=(uint8_t)(i+1);
   int_rsuser(0,NULL);
   assert(received==code[i]&&rxstate==1&&clk_start_rx==maincpu_clk);
   assert(alarm_instance.next==maincpu_clk+char_clk_ticks);
  }
  physical_result=0;maincpu_clk=clk_start_rx+char_clk_ticks;int_rsuser(0,NULL);
  assert(rxstate==0);
  // Switching baud clears a partially received/transmitted old frame.
  physical_result=1;int_rsuser(0,NULL);rsuser_set_tx_bit(0);
  assert(!set_baudrate(rates[(rate+1)%4],NULL));
  assert(!rxstate&&!clk_start_tx&&!clk_start_rx&&!valid&&txbit==1);
  physical_result=0;
 }
 }
 // Resource setters pass each supported format to the physical interface.
 // These checks exercise configuration plumbing, not new waveform coverage.
 int opens_before=physical_opens,network_before=network_opens;
 for(int parity=0;parity<3;++parity)for(int bits=7;bits<=8;++bits)for(int stops=1;stops<=2;++stops){
  assert(!set_parity(parity,NULL));assert(!set_data_bits(bits,NULL));assert(!set_stop_bits(stops,NULL));
  assert(parity_value==(unsigned)parity&&data_bits_value==(unsigned)bits&&stop_bits_value==(unsigned)stops);
 }
 assert(physical_opens==opens_before&&network_opens==network_before);
 int requests_before=framing_requests;
 assert(set_parity(-1,NULL)==-1&&set_parity(3,NULL)==-1);
 assert(set_data_bits(6,NULL)==-1&&set_data_bits(9,NULL)==-1);
 assert(set_stop_bits(0,NULL)==-1&&set_stop_bits(3,NULL)==-1);
 assert(framing_requests==requests_before&&parity_value==2&&data_bits_value==8&&stop_bits_value==2);
 // Reopening with a saved non-default format must retain all requested fields.
 int saved_baud=baud_value;
 rsuser_reset();assert(physical_opens==opens_before+1&&baud_value==saved_baud);
 assert(parity_value==2&&data_bits_value==8&&stop_bits_value==2);
 // A framing transition clears partial guest samples without reopening USB.
 buf=0;valid=5;rxstate=1;clk_start_tx=clk_start_rx=clk_start_bit=clk_end_tx=maincpu_clk;
 assert(!set_parity(0,NULL));
 assert(!valid&&!rxstate&&!clk_start_tx&&!clk_start_rx&&!clk_start_bit&&!clk_end_tx&&txbit==1);
 assert(!set_data_bits(8,NULL));assert(!set_stop_bits(1,NULL));
 assert(parity_value==0&&data_bits_value==8&&stop_bits_value==1);
 waveform_regression();
 ccgms_up9600_idle_regression();
 ccgms_up9600_receive_order_regression();
 assert(set_baudrate(4800,NULL)==-1);
 assert(!set_baudrate(9600,NULL));
 assert(baud_value==9600);
 int old=physical_opens;rsuser_reset();assert(physical_closes&&physical_opens==old+1&&fd==RSUSER_FTDI_FD);
 assert(parity_value==0&&data_bits_value==8&&stop_bits_value==1);
 /* Restore the legacy bit-bang speed before switching to the modem. */
 assert(!set_baudrate(2400,NULL));
 assert(baud_value==2400);
 assert(!set_enable(0,NULL));assert(!alarm_instance.active&&fd==-1);
 old=network_opens;assert(!set_enable(1,NULL));assert(network_opens==old);
 assert(!set_ftdi(0,NULL));assert(!rsuser_enabled&&network_opens==old);assert(!set_enable(1,NULL));assert(network_opens==old+1);
 requests_before=framing_requests;opens_before=physical_opens;
 int modem_opens=network_opens,modem_closes=network_closes,modem_baud=rsuser_baudrate;
 int modem_ticks=char_clk_ticks,modem_bits=bit_clk_ticks;
 assert(!set_parity(1,NULL));assert(!set_data_bits(7,NULL));assert(!set_stop_bits(2,NULL));
 assert(framing_requests==requests_before&&physical_opens==opens_before);
 assert(network_opens==modem_opens&&network_closes==modem_closes&&fd==7);
 assert(rsuser_baudrate==modem_baud&&char_clk_ticks==modem_ticks&&bit_clk_ticks==modem_bits&&frame_bits()==10);
 assert(parity_value==0&&data_bits_value==8&&stop_bits_value==1);
 // Exercise real legacy TX/RX with physical-only resources set to 7E2.
 int legacy_writes=network_writes,usb_writes=physical_writes;
 frame(0xa5);assert(network_writes==legacy_writes+1&&physical_writes==usb_writes);
 network_result=1;maincpu_clk+=100000;int_rsuser(0,NULL);assert(rxstate==1);
 CLOCK legacy_start=clk_start_rx;int legacy_wave[12];assert(uart_bits(0xa5,8,0,1,legacy_wave)==10);
 for(int cell=0;cell<10;++cell){maincpu_clk=legacy_start+cell*bit_clk_ticks+bit_clk_ticks/2;
  assert(rsuser_get_rx_bit()==legacy_wave[cell]);}
 network_result=0;maincpu_clk=alarm_instance.next;int_rsuser(0,NULL);
 assert(!rxstate&&received==0xa5&&alarm_instance.next==maincpu_clk+char_clk_ticks/8);
 assert(!set_parity(0,NULL));assert(!set_data_bits(8,NULL));assert(!set_stop_bits(1,NULL));
 assert(framing_requests==requests_before);
 network_result=-1;flags=0;int_rsuser(0,NULL);assert(!flags);
 selection_regression();
 machine_class=VICE_MACHINE_VIC20;assert(set_ftdi(1,NULL)==-1);
 assert(set_ftdi(E64_RS232_USB_AUTO,NULL)==-1);
 puts("PASS VICE: production rsuser, default/network isolation, all 256 TX frames, RX alarms, PAL/NTSC 300/600/1200/2400 bit timing, continuous RX pacing and duplex, partial-frame baud reset, baud validation, reset/disable, no error-as-data");
}
