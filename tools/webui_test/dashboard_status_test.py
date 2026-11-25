#!/usr/bin/env python3
"""Run the production status handler with changing live settings."""
import json
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
overlay = (root / "third_party/vice-3.3/src/arch/raspi/vice_overlay.c").read_text()
drive_leds = overlay[overlay.index("// One word per native drive slot:"):
                     overlay.index("// Called by VICE to show tape counter text")]
source = (root / "src/webui/webui.cpp").read_text()
handler = source[source.index("void HandleDriveActivity("):source.index("// Server lifecycle flags")]
json_text = source[source.index("void JsonText("):source.index("// Firmware identities")]
fixture = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include "fan_control.h"
#include "uiapi.h"
#include "network_prefs.h"

#define WEBUI_HOSTNAME "E64"
#define CONFIGS_MAX_NAME_LEN 48
using boolean = bool;
struct CSocket {};
struct CTimer {
  static CTimer *Get() { static CTimer timer; return &timer; }
  unsigned GetUptime() { return 42; }
};
struct CMachineInfo {
  static CMachineInfo *Get() { static CMachineInfo info; return &info; }
  const char *GetMachineName() { return "Raspberry Pi 3B+"; }
};
struct ConfigInfo { const char *id, *name; };
const ConfigInfo *configs_running() {
  static const ConfigInfo config = {"default", "Special \"name\""};
  return &config;
}
const char *menu_configs_start_error() { return ""; }
bool configs_in_use() { return true; }
const ConfigInfo *WebUiMachineGet() {
  static const ConfigInfo machine = {"c64", "C64"};
  return &machine;
}
int WebUiMachineCapsJson(char *out, unsigned size) { return snprintf(out, size, "{}"); }
void SendText(CSocket *, int, const char *, const char *) { assert(false); }
void SendResponse(CSocket *, int status, const char *, const char *type,
                  const char *body, unsigned length) {
  assert(status == 200 && !strcmp(type, "application/json") && length == strlen(body));
  puts(body);
}

int modem_base;
int ftdi_error;
FtdiSettings live_ftdi;
const char *audio;
int circle_get_acia_network_address() { return modem_base; }
int emux_get_ftdi_settings(FtdiSettings *settings) {
  *settings = live_ftdi;
  return ftdi_error;
}
const char *circle_get_audio_output() { return audio; }
int circle_get_network_ip_address(char *out, unsigned size) {
  return snprintf(out, size, "192.0.2.2") > 0;
}
int circle_get_network_status() { return 1; }
const char *NetStatusText(int) { return "Connected"; }
void SocTempField(char *out, unsigned size) { snprintf(out, size, "52.5"); }
void ThrottledField(char *out, unsigned size) { snprintf(out, size, "0"); }
const char *bmc64_version_string() { return "test"; }
int menu_joysticks_reversed() { return 0; }
void bmc64_webui_emulator_status(int *, int *, int *, int *, int *, int *, int *, int *) {}
void menu_web_hotkey_label(int, char *out, unsigned size) {
  memset(out, '\\', size - 1);
  out[size - 1] = 0;
}
void fan_get_status(FanStatus *fan) { *fan = {{1,55,50},1,1,0,0}; }
'''
native = r'''
int native_led_calls;
int native_enable_mask;
void emux_enable_drive_status(int state, int *) { native_enable_mask = state; }
void emux_display_drive_led(int, unsigned int, unsigned int) { ++native_led_calls; }
'''
main = r'''
int main() {
  CSocket socket;
  modem_base = 0xd700;
  live_ftdi = {17, 9600, 0, 8, 1, 1};
  audio = "HDMI";
  ui_enable_drive_status(
      static_cast<ui_drive_enable_t>(UI_DRIVE_ENABLE_0 | UI_DRIVE_ENABLE_1), nullptr);
  ui_display_drive_led(0, 1, 0);
  ui_display_drive_led(0, 0, 0);
  ui_display_drive_led(1, 1000, 1000);
  ui_display_drive_led(2, 1000, 0);
  ui_display_drive_led(-1, 1000, 0);
  ui_display_drive_led(4, 1000, 0);
  assert(native_led_calls == 4);
  assert(bmc64_webui_drive_activity(4) == 0);
  assert(bmc64_webui_drive_activity(~0u) == 0);
  HandleDriveActivity(&socket);
  HandleStatus(&socket);
  ui_display_drive_led(0, 0, 1000);
  ui_enable_drive_status(UI_DRIVE_ENABLE_0, nullptr);
  assert(native_enable_mask == UI_DRIVE_ENABLE_0);
  HandleDriveActivity(&socket);
  modem_base = 0xdf80;
  live_ftdi = {2, 1200, 1, 7, 2, 1};
  audio = "Analog";
  HandleStatus(&socket);
  modem_base = 0;
  live_ftdi.parity = 2;
  audio = "Auto";
  HandleStatus(&socket);
  live_ftdi.enabled = 0;
  HandleStatus(&socket);
  ftdi_error = 1;
  HandleStatus(&socket);
  ui_enable_drive_status(static_cast<ui_drive_enable_t>(12), nullptr);
  ui_display_drive_led(3, 1000, 0);
  HandleDriveActivity(&socket);
  for (unsigned int &word : web_drive_activity) __atomic_store_n(&word, ~0u, __ATOMIC_RELAXED);
  HandleDriveActivity(&socket);
}
'''
with tempfile.TemporaryDirectory(prefix="e64-dashboard-status-", dir=root / "build") as directory:
    source_file = Path(directory) / "status.cpp"
    source_file.write_text(fixture + native + drive_leds + json_text + handler + main)
    executable = Path(directory) / "status"
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    "-I" + str(root / "src"),
                    "-I" + str(root / "third_party/vice-3.3/src"), source_file, "-o", executable], check=True)
    rows = [json.loads(row) for row in subprocess.check_output([executable], text=True).splitlines()]
assert [row for row in rows if isinstance(row, list)] == [
    [5, 7, 0, 0], [5, 4, 0, 0], [4, 4, 1, 7], [4294967295] * 4,
]
rows = [row for row in rows if isinstance(row, dict)]
assert [row["drive_activity"] for row in rows] == [
    [5, 7, 0, 0],  # Completed pulse, second mechanism active, disabled slots.
    [5, 4, 0, 0],  # Error-only signal leaves slot 0 dim, disabled slot retains its count.
    [5, 4, 0, 0],
    [5, 4, 0, 0],
    [5, 4, 0, 0],
]
assert [(row["virtual_modem_address"], row["ftdi_rs232"], row["audio_output"]) for row in rows] == [
    ("$D700", "9600,N,8,1", "HDMI"),
    ("$DF80", "1200,E,7,2", "Analog"),
    ("Off", "1200,O,7,2", "Auto"),
    ("Off", "Off", "Auto"),
    ("Off", "", "Auto"),
]
assert all(row["ip"] == "192.0.2.2" and row["soc_temp_c"] == 52.5 and
           len(row["hotkeys"]) == 8 and row["config_name"] == 'Special "name"' for row in rows)
print("PASS native bounds, both status handlers for pulse, dual slot, error LED, disabled drive, and serial/audio settings")
