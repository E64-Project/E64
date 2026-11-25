#include "gpio_recovery.h"
static int key(const GpioRecoveryIO *io, unsigned pa, unsigned pb) {
 io->row(io->context,pa,1);
 io->delay_us(io->context,10);
 int pressed = !io->read(io->context,pb);
 io->row(io->context,pa,0);
 return pressed;
}
int gpio_recovery_sample(const GpioRecoveryIO *io) {
 // With no PA driven, a passive keyboard must read high even with keys held.
 // Grounded/shared joystick inputs are not evidence of a matrix keypress.
 if (!io->read(io->context,5)) return 0;
 unsigned start=io->time_us(io->context), stable_since=start;
 int previous=0;
 unsigned limit=50000;
 // A real clock includes GPIO mode/pull-up settling, not just our delays.
 // The iteration cap also bounds work if a backend clock fails to advance.
 for (unsigned i=0;i<6000;i++) {
  unsigned before=io->time_us(io->context);
  if (before-start>=limit) break;
  int commodore=key(io,7,5);
  // Shift is not sampled: C= always requests protected Default NTSC.
  int choice=commodore ? 1 : 0;
  unsigned now=io->time_us(io->context);
  if (choice!=previous) stable_since=now;
  previous=choice;
  unsigned elapsed=now-start;
  if (elapsed>=limit) break;
  unsigned pause=now-before<1000 ? 1000-(now-before) : 0;
  if (pause>limit-elapsed) pause=limit-elapsed;
  if (pause) io->delay_us(io->context,pause);
 }
 return io->time_us(io->context)-stable_since>=20000 ? previous : 0;
}
