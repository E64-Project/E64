#include "fan_control.h"
#include <circle/gpiopin.h>
#include <circle/spinlock.h>
#include <circle/timer.h>
#include <circle/bcmpropertytags.h>

namespace {
CSpinLock lock;
CGPIOPin *pin;
FanStatus state = {{0,55,50},0,0,0,0};
FanSettings requested;
unsigned last_poll;
bool started, sampled, stopped;
void output(int on) {
  if (pin && state.output != on) pin->Write(on ? HIGH : LOW);
  state.output = pin ? on : 0;
}
}
extern "C" int fan_dpi_allowed(void) {
#if defined(RASPI_C64)
  return 0; // E64 V1 has a fan connection even when automatic control is disabled.
#else
  return 1;
#endif
}
extern "C" void fan_gpio_init(int dpi) {
  // DPI and all non-E64 targets keep their original GPIO ownership.
#if defined(RASPI_C64) && RASPPI <= 3
  if (dpi || pin) return;
  pin = new CGPIOPin(FAN_GPIO, GPIOModeInputPullDown);
  pin->Write(LOW); // preload latch before switching direction (no high pulse)
  pin->SetMode(GPIOModeOutput, FALSE);
  state.available = 1;
#else
  (void)dpi;
#endif
}
extern "C" void fan_start(void) {
  FanSettings settings;
  int error = fan_prefs_load(&settings);
  lock.Acquire();
  state.settings = settings;
  state.error = error;
  started = true;
  lock.Release();
  fan_service();
}
extern "C" void fan_get_status(FanStatus *s) {
  lock.Acquire(); *s = state; lock.Release();
}
static int request_settings(const FanSettings *p, const FanSettings *expected) {
  if (!fan_settings_valid(p)) return 1;
  lock.Acquire();
  if (!state.available || !started || stopped || state.pending ||
      (expected && (expected->enabled != state.settings.enabled ||
                    expected->on_c != state.settings.on_c ||
                    expected->off_c != state.settings.off_c))) {
    lock.Release(); return 1;
  }
  if (p->enabled == state.settings.enabled && p->on_c == state.settings.on_c &&
      p->off_c == state.settings.off_c && !state.error) { lock.Release(); return 0; }
  requested = *p;
  state.pending = 1;
  state.error = 0;
  lock.Release();
  return 0;
}
extern "C" int fan_request(const FanSettings *p) {
  return request_settings(p, nullptr);
}
extern "C" int fan_request_if_current(const FanSettings *p, const FanSettings *expected) {
  return expected ? request_settings(p, expected) : 1;
}
extern "C" void fan_service(void) {
  lock.Acquire();
  if (!started || stopped || !state.available) { lock.Release(); return; }
  int pending = state.pending;
  FanSettings next = requested;
  lock.Release();
  // No filesystem or mailbox work under the lock or on the emulator core.
  if (pending) {
    int error = fan_prefs_save(&next);
    lock.Acquire();
    state.error = error;
    if (!error && !stopped) {
      state.settings = next;
      sampled = false;
    }
    state.pending = 0;
    lock.Release();
  }
  lock.Acquire();
  if (stopped) { lock.Release(); return; }
  if (state.settings.enabled != FAN_AUTO) {
    output(state.settings.enabled == FAN_ON);
    sampled = false; lock.Release(); return;
  }
  unsigned now = CTimer::GetClockTicks();
  if (sampled && (unsigned)(now - last_poll) < 1000000u) {
    lock.Release(); return;
  }
  last_poll = now; sampled = true;
  lock.Release();
  CBcmPropertyTags tags;
  TPropertyTagTemperature tag = {};
  tag.nTemperatureId = TEMPERATURE_ID;
  int temp = tags.GetTag(PROPTAG_GET_TEMPERATURE, &tag, sizeof(tag), sizeof(u32))
    ? (int)tag.nValue : 0;
  lock.Acquire();
  if (!stopped) output(fan_decide(&state.settings, state.available, state.output, temp));
  lock.Release();
}
extern "C" void fan_prepare_shutdown(void) {
  lock.Acquire();
  stopped = true;
  // Keep cooling during halt/reset if control was enabled. Reset/boot firmware
  // may subsequently reset the pin; an external pulldown is required.
  if (state.available) output(state.settings.enabled != FAN_OFF);
  lock.Release();
}
