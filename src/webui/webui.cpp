#include "web_datasette.h"
#include "../fan_control.h"
//
// webui.cpp
//
// Minimal HTTP/1.1 server for the BMC64 LAN web UI. Runs as a single
// Circle scheduler task on the kernel/networking core (core 0). It never
// runs on the emulator core; long I/O loops yield so the cooperative
// scheduler keeps servicing the network stack and other tasks.
//
// Endpoints: GET static assets, GET /api/status, POST /api/reboot,
// POST /api/shutdown, POST /api/reset, GET /api/volumes, GET /api/fs/list, GET /api/fs/download,
// POST /api/fs/upload, POST /api/fs/save, POST /api/fs/delete,
// POST /api/fs/mkdir, POST /api/fs/rename, POST /api/fs/autostart,
// POST /api/configs/start, POST /api/webui/disable.
//
// When a PIN is configured, every request must carry HTTP Basic Auth
// (Authorization: Basic base64(<user>:<pin>)); the username is ignored.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "webui.h"

#if BMC64_WEBUI

#include "webui_assets.h"
#include "webui_fs.h"
#include "webui_http.h"
#include "webui_machine.h"
#include "../configs/configs.h"
#include "../network_prefs.h"

#include <circle/bcmpropertytags.h>
#include <circle/logger.h>
#include <circle/machineinfo.h>
#include <circle/net/in.h>
#include <circle/net/ipaddress.h>
#include <circle/net/netsubsystem.h>
#include <circle/net/socket.h>
#include <circle/sched/scheduler.h>
#include <circle/sched/task.h>
#include <circle/timer.h>
#include <circle/types.h>

#include <stdio.h>
#include <string.h>

// circle_get_network_status() / circle_get_network_ip_address() are the
// C bridge already implemented in src/vice_network.cpp.
extern "C" int circle_get_network_status(void);
extern "C" int circle_get_acia_network_address(void);
extern "C" int emux_get_ftdi_settings(FtdiSettings *settings);
extern "C" const char *circle_get_audio_output(void);
extern "C" int circle_get_network_ip_address(char *address,
                                             unsigned int address_size);
// BMC64 version string; single source of truth is menu.c's VERSION_STRING.
extern "C" const char *bmc64_version_string(void);
extern "C" int menu_joysticks_reversed(void);
extern "C" void menu_web_hotkey_label(int slot, char *out, unsigned size);
extern "C" void bmc64_webui_emulator_status(int *warp, int *d8, int *d9,
                                             int *d10, int *d11, int *ieee488,
                                             int *reu, int *reu_size);
extern "C" unsigned int bmc64_webui_drive_activity(unsigned int slot);
// Queues a "quick function" for the emulator main loop (interrupt safe;
// see third_party/common/circle.h / ui.c).
extern "C" void emu_quick_func_interrupt(int button_assignment);
// Queues a reboot or power off for the emulator main loop, which writes out
// the disk images first (third_party/common/menu_power.c).
extern "C" void emu_power_interrupt(int power_off);
// Queues Switch to / Start once of a config for the emulator main loop
// (third_party/common/circle.h), and why the last one failed
// (third_party/common/menu_configs.h).
extern "C" int emu_config_start_interrupt(const char *id, int once);
extern "C" int emu_config_protection_interrupt(const char *id, int on, int confirmed_off);
extern "C" unsigned emu_config_logical_interrupt(const char *id, int legacy);
extern "C" const char *menu_configs_start_error(void);
extern "C" void menu_configs_clear_start_error(void);
extern "C" void menu_configs_delete_status(unsigned *serial, int *state,
    char *id, unsigned id_size, char *error, unsigned error_size);
// BTN_ASSIGN_RESET_HARD2 from third_party/common/circle.h: hard reset the
// emulated machine with no on-screen confirmation dialog.
#define WEBUI_QUICKFUNC_RESET_HARD 916
#define WEBUI_QUICKFUNC_RESET_SOFT 918
#define WEBUI_QUICKFUNC_WARP        3
// BTN_ASSIGN_SWAP_PORTS: identical to native Quick Settings / hotkey dispatch.
#define WEBUI_QUICKFUNC_SWAP_PORTS  5

#define WEBUI_LOG              "webui"
#define WEBUI_PORT             80
#define WEBUI_ALT_PORT         8080
#define WEBUI_TASK_STACK       0x10000
#define WEBUI_RECV_TIMEOUT_US  8000000
#define WEBUI_REQUEST_MAX      4096
#define WEBUI_LISTEN_BACKLOG   8
#define WEBUI_PIN_MAX          16
#define WEBUI_AUTH_FAIL_MS     500  // slow brute-forcing a wrong PIN

// CNetSubSystem is created with this name in src/viceapp.cpp.
#define WEBUI_HOSTNAME         "e64"

namespace {

// Keep in sync with the CIRCLE_NETWORK_* enum in third_party/common/circle.h.
const char *NetStatusText(int status) {
  switch (status) {
  case 0:  return "disabled";
  case 1:  return "Ethernet initializing";
  case 2:  return "waiting for DHCP";
  case 3:  return "connected (Ethernet)";
  case 4:  return "Ethernet unavailable";
  case 5:  return "Ethernet init failed";
  case 6:  return "Wi-Fi config missing";
  case 7:  return "Wi-Fi device initializing";
  case 8:  return "Wi-Fi device init failed";
  case 9:  return "Wi-Fi network init failed";
  case 10: return "Wi-Fi WPA initializing";
  case 11: return "Wi-Fi WPA init failed";
  case 12: return "Wi-Fi connecting";
  case 13: return "connected (Wi-Fi)";
  case 14: return "Wi-Fi connection timeout";
  case 15: return "Wi-Fi unavailable";
  case 16: return "Wi-Fi device not initialized";
  case 17: return "Wi-Fi unsupported";
  case 18: return "Wi-Fi firmware missing";
  default: return "unknown";
  }
}

using webhttp::SendResponse;
using webhttp::SendText;

// Case-insensitive test whether s begins with the (already lowercase) prefix.
boolean CiPrefix(const char *s, const char *lower_prefix) {
  for (; *lower_prefix != '\0'; s++, lower_prefix++) {
    char c = *s;
    if (c >= 'A' && c <= 'Z') {
      c = (char) (c + 32);
    }
    if (c != *lower_prefix) {
      return FALSE;
    }
  }
  return TRUE;
}

// Value of the Content-Length header in a raw request, or -1 if absent.
long ParseContentLength(const char *request) {
  const char *p = request;
  while (*p != '\0') {
    if (CiPrefix(p, "content-length:")) {
      p += 15;
      while (*p == ' ' || *p == '\t') {
        p++;
      }
      long value = 0;
      boolean any = FALSE;
      while (*p >= '0' && *p <= '9') {
        value = value * 10 + (*p - '0');
        p++;
        any = TRUE;
      }
      return any ? value : -1;
    }
    const char *nl = strstr(p, "\r\n");
    if (nl == 0) {
      break;
    }
    p = nl + 2;
  }
  return -1;
}

// TRUE if the raw request has a header whose name-and-colon matches
// name_colon (lower case, e.g. "x-bmc64-web:"). Stops at the blank line so
// body text can't pose as a header.
boolean HasHeader(const char *request, const char *name_colon) {
  const char *p = request;
  while (*p != '\0' && !(p[0] == '\r' && p[1] == '\n')) {
    if (CiPrefix(p, name_colon)) {
      return TRUE;
    }
    const char *nl = strstr(p, "\r\n");
    if (nl == 0) {
      break;
    }
    p = nl + 2;
  }
  return FALSE;
}

const struct webui_asset *FindAsset(const char *path) {
  for (unsigned i = 0; i < g_webui_asset_count; i++) {
    if (strcmp(g_webui_assets[i].path, path) == 0) {
      return &g_webui_assets[i];
    }
  }
  return 0;
}

// SoC temperature as a JSON number ("47.2") into out, or "null" if the
// VideoCore mailbox query fails (e.g. QEMU).
void SocTempField(char *out, unsigned out_size) {
  CBcmPropertyTags tags;
  TPropertyTagTemperature tag;
  tag.nTemperatureId = TEMPERATURE_ID;
  if (tags.GetTag(PROPTAG_GET_TEMPERATURE, &tag, sizeof(tag), sizeof(u32)) &&
      tag.nValue > 0) {
    snprintf(out, out_size, "%u.%01u", tag.nValue / 1000,
             (tag.nValue % 1000) / 100);
  } else {
    strncpy(out, "null", out_size);
    out[out_size - 1] = '\0';
  }
}

// Raspberry Pi firmware "get_throttled" bitmask, forwarded raw and
// decoded client side. These are independent conditions: bit 0/16
// under-voltage (a 5V supply problem), bit 2/18 the ARM clock actually
// being throttled (from under-voltage or the 85C hard thermal limit),
// bit 1/17 the turbo frequency being capped, bit 3/19 the Pi 3B+
// "soft" temp limit (config.txt temp_soft_limit, default 60C): a
// partial throttle easing the ARM clock from 1.4GHz to 1.2GHz. Low
// bits are "now", bits 16-19 "since boot".
// "null" if the mailbox query is unavailable (e.g. QEMU).
void ThrottledField(char *out, unsigned out_size) {
  CBcmPropertyTags tags;
  TPropertyTagSimple tag;
  if (tags.GetTag(PROPTAG_GET_THROTTLED, &tag, sizeof(tag))) {
    snprintf(out, out_size, "%lu", (unsigned long) tag.nValue);
  } else {
    strncpy(out, "null", out_size);
    out[out_size - 1] = '\0';
  }
}

// Copies s into out as the inside of a JSON string. Config names come from
// the menu, so they're plain text; anything else is replaced.
void JsonText(const char *s, char *out, unsigned out_size) {
  unsigned n = 0;
  for (; *s != '\0' && n + 2 < out_size; s++) {
    unsigned char c = (unsigned char) *s;
    if (c == '"' || c == '\\') {
      out[n++] = '\\';
      out[n++] = (char) c;
    } else {
      out[n++] = (c < 0x20 || c >= 0x80) ? '?' : (char) c;
    }
  }
  out[n] = '\0';
}

// Firmware identities or a valid user Config identity.
boolean IsConfigId(const char *id) {
  if (!id || !strcmp(id,"main")) return FALSE;
  if (configs_is_factory(id)) return TRUE;
  unsigned length = 0;
  for (; id[length] != '\0'; length++) {
    char c = id[length];
    if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-')) {
      return FALSE;
    }
  }
  return length > 0 && length <= CONFIGS_MAX_ID_LEN;
}

void HandleDriveActivity(CSocket *socket) {
  // Four unsigned 32-bit words, plus JSON punctuation and terminator.
  char body[48];
  int length = snprintf(body, sizeof(body), "[%u,%u,%u,%u]",
                        bmc64_webui_drive_activity(0), bmc64_webui_drive_activity(1),
                        bmc64_webui_drive_activity(2), bmc64_webui_drive_activity(3));
  if (length < 0 || (unsigned) length >= sizeof(body)) {
    SendText(socket, 500, "Internal Server Error", "drive activity encode error\n");
    return;
  }
  SendResponse(socket, 200, "OK", "application/json", body, (unsigned) length);
}

void HandleStatus(CSocket *socket) {
  char ip[32];
  boolean have_ip = circle_get_network_ip_address(ip, sizeof(ip)) != 0;
  int net_status = circle_get_network_status();
  unsigned uptime = CTimer::Get()->GetUptime();
  const char *model = CMachineInfo::Get()->GetMachineName();

  char soc_temp[16];
  char throttled[16];
  SocTempField(soc_temp, sizeof(soc_temp));
  ThrottledField(throttled, sizeof(throttled));

  // The config running now (docs/CONFIGS.md).
  const ConfigInfo *config = configs_running();
  char config_name[2 * CONFIGS_MAX_NAME_LEN + 1];
  JsonText(config->name, config_name, sizeof(config_name));
  char config_error[128];
  JsonText(menu_configs_start_error(), config_error, sizeof(config_error));

  // What this machine's web UI can do (webui_machine.h).
  char caps[256];
  if (WebUiMachineCapsJson(caps, sizeof(caps)) < 0) {
    SendText(socket, 500, "Internal Server Error", "status encode error\n");
    return;
  }

  int warp = -1, d8 = -1, d9 = -1, d10 = -1, d11 = -1, ieee488 = -1;
  int reu = -1, reu_size = -1;
  bmc64_webui_emulator_status(&warp, &d8, &d9, &d10, &d11,
                               &ieee488, &reu, &reu_size);

  char modem_address[16] = "Off";
  const int modem_base = circle_get_acia_network_address();
  if (modem_base > 0)
    snprintf(modem_address, sizeof(modem_address), "$%04X", (unsigned)modem_base);

  char ftdi_status[48] = "";
  FtdiSettings ftdi;
  if (emux_get_ftdi_settings(&ftdi) == 0) {
    const char parity[] = {'N', 'E', 'O'};
    if (!ftdi.adapter || !ftdi.enabled)
      snprintf(ftdi_status, sizeof(ftdi_status), "Off");
    else if ((unsigned)ftdi.parity < sizeof(parity))
      snprintf(ftdi_status, sizeof(ftdi_status), "%d,%c,%d,%d",
               ftdi.baud, parity[ftdi.parity], ftdi.data_bits, ftdi.stop_bits);
  }

  char hotkeys[768];
  unsigned used = 0;
  hotkeys[used++] = '[';
  for (int slot = 0; slot < 8; slot++) {
    char label[36], escaped[73];
    menu_web_hotkey_label(slot, label, sizeof(label));
    JsonText(label, escaped, sizeof(escaped));
    used += snprintf(hotkeys + used, sizeof(hotkeys) - used,
                     "%s\"%s\"", slot ? "," : "", escaped);
  }
  snprintf(hotkeys + used, sizeof(hotkeys) - used, "]");
  FanStatus fan;
  fan_get_status(&fan);
  const char *fan_output = fan.available && fan.settings.enabled != FAN_OFF ?
    (fan.output ? "true" : "false") : "null";
  char body[2048];
  int length = snprintf(
      body, sizeof(body),
      "{\"hostname\":\"%s\",\"version\":\"%s\",\"machine\":\"%s\","
      "\"model\":\"%s\",\"ip\":\"%s\",\"net_status\":%d,\"net_text\":\"%s\","
      "\"uptime_secs\":%u,\"soc_temp_c\":%s,\"throttled\":%s,"
      "\"joystick_swap\":%d,\"warp\":%d,\"ieee488\":%d,\"reu\":%d,\"reu_size\":%d,"
      "\"virtual_modem_address\":\"%s\",\"ftdi_rs232\":\"%s\",\"audio_output\":\"%s\","
      "\"hotkeys\":%s,\"fan_on\":%s,\"fan_available\":%d,\"fan_enabled\":%d,\"fan_on_c\":%d,\"fan_off_c\":%d,\"fan_pending\":%d,\"fan_error\":%d,\"drives\":[%d,%d,%d,%d],"
      "\"drive_activity\":[%u,%u,%u,%u],"
      "\"config_id\":\"%s\",\"config_name\":\"%s\","
      "\"configs_in_use\":%s,\"config_error\":\"%s\",\"caps\":%s}",
      WEBUI_HOSTNAME, bmc64_version_string(), WebUiMachineGet()->name,
      model != 0 ? model : "",
      have_ip ? ip : "", net_status, NetStatusText(net_status), uptime,
      soc_temp, throttled, menu_joysticks_reversed(), warp, ieee488, reu, reu_size,
      modem_address, ftdi_status, circle_get_audio_output(),
      hotkeys, fan_output, fan.available, fan.settings.enabled != FAN_OFF, fan.settings.on_c,
      fan.settings.off_c, fan.pending, fan.error, d8, d9, d10, d11,
      bmc64_webui_drive_activity(0), bmc64_webui_drive_activity(1),
      bmc64_webui_drive_activity(2), bmc64_webui_drive_activity(3),
      config->id, config_name,
      configs_in_use() ? "true" : "false", config_error, caps);
  if (length < 0 || (unsigned) length >= sizeof(body)) {
    SendText(socket, 500, "Internal Server Error", "status encode error\n");
    return;
  }
  SendResponse(socket, 200, "OK", "application/json", body, (unsigned) length);
}

// Server lifecycle flags. s_started guards against a second task;
// g_webui_stop is set by POST /api/webui/disable to end the accept loop.
boolean s_started = FALSE;
boolean g_webui_stop = FALSE;

// HTTP Basic Auth PIN; empty means the server is open.
char s_pin[WEBUI_PIN_MAX] = {0};

int Base64Value(char c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  return -1;
}

// Decode base64 src into dst (NUL-terminated). Returns length, or -1 on
// invalid input or overflow.
int Base64Decode(const char *src, char *dst, unsigned dst_size) {
  unsigned out = 0;
  int quad[4];
  int have = 0;
  for (const char *p = src; *p != '\0'; p++) {
    if (*p == '=' || *p == ' ' || *p == '\r' || *p == '\n' || *p == '\t') {
      break;
    }
    int v = Base64Value(*p);
    if (v < 0) return -1;
    quad[have++] = v;
    if (have == 4) {
      if (out + 3 >= dst_size) return -1;
      dst[out++] = (char) ((quad[0] << 2) | (quad[1] >> 4));
      dst[out++] = (char) ((quad[1] << 4) | (quad[2] >> 2));
      dst[out++] = (char) ((quad[2] << 6) | quad[3]);
      have = 0;
    }
  }
  if (have == 2) {
    if (out + 1 >= dst_size) return -1;
    dst[out++] = (char) ((quad[0] << 2) | (quad[1] >> 4));
  } else if (have == 3) {
    if (out + 2 >= dst_size) return -1;
    dst[out++] = (char) ((quad[0] << 2) | (quad[1] >> 4));
    dst[out++] = (char) ((quad[1] << 4) | (quad[2] >> 2));
  } else if (have != 0) {
    return -1;
  }
  dst[out] = '\0';
  return (int) out;
}

enum { AUTH_OK, AUTH_MISSING, AUTH_BAD };

// Check HTTP Basic Auth against s_pin. Returns AUTH_OK when no PIN is
// set, or when the request's Authorization password matches.
int CheckAuth(const char *request) {
  if (s_pin[0] == '\0') {
    return AUTH_OK;
  }

  const char *p = request;
  const char *value = 0;
  while (*p != '\0') {
    if (CiPrefix(p, "authorization:")) {
      value = p + 14;
      break;
    }
    const char *nl = strstr(p, "\r\n");
    if (nl == 0) break;
    p = nl + 2;
  }
  if (value == 0) {
    return AUTH_MISSING;
  }

  while (*value == ' ' || *value == '\t') value++;
  if (!CiPrefix(value, "basic ")) {
    return AUTH_BAD;
  }
  value += 6;
  while (*value == ' ') value++;

  char decoded[128];
  if (Base64Decode(value, decoded, sizeof(decoded)) < 0) {
    return AUTH_BAD;
  }
  const char *colon = strchr(decoded, ':');
  const char *pass = colon != 0 ? colon + 1 : decoded;

  if (strlen(pass) != strlen(s_pin)) {
    return AUTH_BAD;
  }
  unsigned diff = 0;
  for (unsigned i = 0; s_pin[i] != '\0'; i++) {
    diff |= (unsigned char) (pass[i] ^ s_pin[i]);
  }
  return diff == 0 ? AUTH_OK : AUTH_BAD;
}

void Send401(CSocket *socket) {
  const char *body = "authentication required\n";
  char header[256];
  int n = snprintf(
      header, sizeof(header),
      "HTTP/1.1 401 Unauthorized\r\n"
      "WWW-Authenticate: Basic realm=\"BMC64 Web UI - any username, PIN as "
      "password\", charset=\"UTF-8\"\r\n"
      "Content-Type: text/plain; charset=utf-8\r\n"
      "Content-Length: %u\r\n"
      "Connection: close\r\n"
      "Cache-Control: no-store\r\n"
      "\r\n",
      (unsigned) strlen(body));
  if (n > 0 && (unsigned) n < sizeof(header) &&
      webhttp::SendAll(socket, header, (unsigned) n)) {
    webhttp::SendAll(socket, body, (unsigned) strlen(body));
  }
}

boolean HandleConnection(CSocket *socket) {
  socket->SetOptionReceiveTimeout(WEBUI_RECV_TIMEOUT_US);

  char request[WEBUI_REQUEST_MAX];
  unsigned length = 0;
  for (;;) {
    if (length >= sizeof(request) - 1) {
      SendText(socket, 431, "Request Header Fields Too Large",
               "request too large\n");
      return FALSE;
    }
    int n = socket->Receive(request + length, sizeof(request) - 1 - length, 0);
    if (n <= 0) {
      return FALSE;  // client closed, timed out, or error
    }
    length += (unsigned) n;
    request[length] = '\0';
    if (strstr(request, "\r\n\r\n") != 0) {
      break;
    }
  }

  // Body bytes that arrived in the same read(s) as the headers, plus the
  // declared body length (for streamed uploads).
  const unsigned char *body =
      (const unsigned char *) (strstr(request, "\r\n\r\n") + 4);
  unsigned body_prefetched = (unsigned) ((const unsigned char *) (request + length) - body);
  long content_length = ParseContentLength(request);

  char method[8];
  char target[WEBUI_REQUEST_MAX];
  if (sscanf(request, "%7s %4095s", method, target) != 2) {
    SendText(socket, 400, "Bad Request", "bad request line\n");
    return FALSE;
  }

  const char *query = "";
  char *question = strchr(target, '?');
  if (question != 0) {
    *question = '\0';
    query = question + 1;
  }

  boolean is_get = strcmp(method, "GET") == 0;
  boolean is_post = strcmp(method, "POST") == 0;

  int auth = CheckAuth(request);
  if (auth != AUTH_OK) {
    if (auth == AUTH_BAD) {
      CScheduler::Get()->MsSleep(WEBUI_AUTH_FAIL_MS);
    }
    Send401(socket);
    return FALSE;
  }

  if (is_get && strcmp(target, "/api/datasette") == 0) {
    WebDatasette s;
    web_datasette_status(&s);
    char filename[6145], response[6900];
    // Preserve UTF-8 media names while escaping JSON syntax/control bytes.
    unsigned used = 0;
    for (const unsigned char *p = (const unsigned char *)s.filename; *p; ++p) {
      if (*p < 0x20) used += snprintf(filename+used,sizeof(filename)-used,"\\u%04x",*p);
      else { if (*p == '"' || *p == '\\') filename[used++] = '\\'; filename[used++] = (char)*p; }
    }
    filename[used] = 0;
    int n = snprintf(response, sizeof(response),
      "{\"supported\":%d,\"attached\":%d,\"writable\":%d,\"counter\":%d,\"mode\":%d,\"motor\":%d,\"pending\":%d,\"error\":%d,\"serial\":%u,\"filename\":\"%s\"}",
      s.supported,s.attached,s.writable,s.counter,s.mode,s.motor,s.pending,s.error,s.serial,filename);
    if (n < 0 || (unsigned)n >= sizeof(response)) SendText(socket,500,"Internal Server Error","datasette encode error\n");
    else SendResponse(socket,200,"OK","application/json",response,(unsigned)n);
    return FALSE;
  }
  if (is_post && strcmp(target, "/api/datasette/control") == 0) {
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket,403,"Forbidden","missing X-BMC64-Web header\n"); return FALSE;
    }
    char action[24];
    const char *actions[] = {"stop","play","record","rewind","forward","reset","zero","eject"};
    int command = -1;
    if (webhttp::QueryParam(query,"action",action,sizeof(action))) {
      for (int i=0;i<8;i++) if (!strcmp(action,actions[i])) command=i;
    }
    if (command < 0) { SendText(socket,400,"Bad Request","invalid Datasette action\n"); return FALSE; }
    int result = web_datasette_queue(command);
    if (result == -1) SendText(socket,501,"Not Implemented","Datasette unavailable\n");
    else if (result <= 0) SendText(socket,409,"Conflict",result == 0 ? "Datasette busy\n" : "TAP required or tape read only\n");
    else SendText(socket,202,"Accepted","queued; check Datasette pending/error state\n");
    return FALSE;
  }

  if (is_get && strcmp(target, "/api/drive-activity") == 0) {
    HandleDriveActivity(socket);
    return FALSE;
  }

  if (is_get && strcmp(target, "/api/status") == 0) {
    HandleStatus(socket);
    return FALSE;
  }

  if (is_get && strcmp(target, "/api/volumes") == 0) {
    WebUiFsVolumes(socket, query);
    return FALSE;
  }

  if (is_get && strcmp(target, "/api/fs/list") == 0) {
    WebUiFsList(socket, query);
    return FALSE;
  }

  if (is_get && strcmp(target, "/api/fs/download-folder") == 0) {
    WebUiFsDownloadFolder(socket, query);
    return FALSE;
  }
  if (is_get && strcmp(target, "/api/fs/download") == 0) {
    WebUiFsDownload(socket, query);
    return FALSE;
  }

  if (is_post && strcmp(target, "/api/fs/upload") == 0) {
    WebUiFsUpload(socket, query, body, body_prefetched, content_length);
    return FALSE;
  }

  if (is_post && strcmp(target, "/api/fs/save") == 0) {
    // Rewrites boot/config files, so demand a header that a cross-site form
    // or no-cors fetch cannot send (it would need a CORS preflight, which
    // this server never grants). Stops another site's page from using the
    // browser's cached PIN to change them.
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n");
      return FALSE;
    }
    WebUiFsSave(socket, query, body, body_prefetched, content_length);
    return FALSE;
  }

  if (is_post && strcmp(target, "/api/fs/delete") == 0) {
    // Deleting a whole folder is far more destructive than one file, so it
    // gets the same cross-site protection as /api/fs/save above.
    char recursive[4];
    if (webhttp::QueryParam(query, "recursive", recursive, sizeof(recursive)) &&
        !HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n");
      return FALSE;
    }
    WebUiFsDelete(socket, query);
    return FALSE;
  }

  if (is_post && (strcmp(target, "/api/fs/mkdir") == 0 ||
                  strcmp(target, "/api/fs/rename") == 0 ||
                  strcmp(target, "/api/fs/transfer") == 0)) {
    // Same cross-site protection as /api/fs/save above.
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n");
      return FALSE;
    }
    if (strcmp(target, "/api/fs/mkdir") == 0) {
      WebUiFsMkdir(socket, query);
    } else if (strcmp(target, "/api/fs/rename") == 0) {
      WebUiFsRename(socket, query);
    } else {
      WebUiFsTransfer(socket, query);
    }
    return FALSE;
  }

  if ((is_get || is_post) && strcmp(target, "/api/fs/raw-cartridge") == 0) {
    if (is_post && !HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n"); return FALSE;
    }
    WebUiFsRawCartridge(socket, query, is_post); return FALSE;
  }

  if (is_post && strcmp(target, "/api/fs/autostart") == 0) {
    WebUiFsAutostart(socket, query);
    return FALSE;
  }

  if (is_post && strcmp(target, "/api/fs/load-tape") == 0) {
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket,403,"Forbidden","missing X-BMC64-Web header\n"); return FALSE;
    }
    WebUiFsLoadTape(socket, query);
    return FALSE;
  }
  if (is_post && strcmp(target, "/api/fs/mount") == 0) {
    WebUiFsMount(socket, query);
    return FALSE;
  }
  if (is_post && strcmp(target, "/api/fs/load-prg") == 0) {
    WebUiFsLoadPrg(socket, query);
    return FALSE;
  }

  if (is_post && strcmp(target, "/api/fan") == 0) {
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n"); return FALSE;
    }
    char enabled[4], on[4], off[4];
    if (!webhttp::QueryParam(query,"enabled",enabled,sizeof(enabled)) ||
        !webhttp::QueryParam(query,"on",on,sizeof(on)) ||
        !webhttp::QueryParam(query,"off",off,sizeof(off)) ||
        (strcmp(enabled,"0") && strcmp(enabled,"1")) ||
        strlen(on)!=2 || strlen(off)!=2 ||
        on[0]<'0' || on[0]>'9' || on[1]<'0' || on[1]>'9' ||
        off[0]<'0' || off[0]>'9' || off[1]<'0' || off[1]>'9') {
      SendText(socket, 400, "Bad Request", "invalid fan settings\n"); return FALSE;
    }
    FanSettings p = {enabled[0]-'0', (on[0]-'0')*10+on[1]-'0', (off[0]-'0')*10+off[1]-'0'};
    if (!fan_settings_valid(&p)) {
      SendText(socket, 400, "Bad Request", "OFF must be below ON; range 30-80 C\n"); return FALSE;
    }
    if (fan_request(&p)) {
      SendText(socket, 409, "Conflict", "fan service busy or unavailable\n"); return FALSE;
    }
    SendText(socket, 202, "Accepted", "fan settings queued; check fan_pending/fan_error\n");
    return FALSE;
  }

  if (is_post && strcmp(target, "/api/webui/disable") == 0) {
    const char *ok = "{\"ok\":true}";
    SendResponse(socket, 200, "OK", "application/json", ok,
                 (unsigned) strlen(ok));
    CLogger::Get()->Write(WEBUI_LOG, LogNotice,
                          "Web UI stop requested via web UI");
    g_webui_stop = TRUE;
    return FALSE;
  }

  if (is_post && (strcmp(target, "/api/reboot") == 0 ||
                  strcmp(target, "/api/shutdown") == 0)) {
    // Same cross-site protection as /api/fs/save: another site must not be
    // able to restart or power off the machine.
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n");
      return FALSE;
    }
    int power_off = strcmp(target, "/api/shutdown") == 0;
    const char *ok = "{\"ok\":true}";
    SendResponse(socket, 202, "Accepted", "application/json", ok,
                 (unsigned) strlen(ok));
    CLogger::Get()->Write(WEBUI_LOG, LogNotice, "%s requested via web UI",
                          power_off ? "Power off" : "Reboot");
    CScheduler::Get()->MsSleep(250);  // give the socket time to flush
    // Queued for the emulator main loop, which writes out the disk images
    // and then restarts or halts.
    emu_power_interrupt(power_off);
    return FALSE;
  }

  if (strcmp(target, "/api/configs/protection") == 0) {
    if (is_post) {
      if (!HasHeader(request, "x-bmc64-web:")) { SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n"); return FALSE; }
      char id[CONFIGS_MAX_ID_LEN+1], on[4]="", confirmed[4]="";
      if (!webhttp::QueryParam(query,"id",id,sizeof(id)) || !IsConfigId(id) ||
          !webhttp::QueryParam(query,"on",on,sizeof(on)) || (strcmp(on,"0") && strcmp(on,"1"))) {
        SendText(socket,400,"Bad Request","invalid protection request\n"); return FALSE;
      }
      webhttp::QueryParam(query,"confirmed",confirmed,sizeof(confirmed));
      if (configs_is_factory(id) && on[0]=='0') { SendText(socket,403,"Forbidden","Factory Config is permanently protected\n"); return FALSE; }
      if (on[0]=='0' && strcmp(confirmed,"1")) { SendText(socket,409,"Conflict","confirmation required\n"); return FALSE; }
      menu_configs_clear_start_error();
      if (!emu_config_protection_interrupt(id,on[0]=='1',!strcmp(confirmed,"1"))) { SendText(socket,409,"Conflict","config request busy\n"); return FALSE; }
      const char *ok="{\"ok\":true}";SendResponse(socket,202,"Accepted","application/json",ok,strlen(ok));
    } else {
      if (!configs_protection_read_begin()) { SendText(socket,409,"Conflict","protection busy\n"); return FALSE; }
      webhttp::CChunkedResponse response(socket,200,"OK","application/json");
      char error[256];JsonText(configs_protection_ready()?menu_configs_start_error():configs_protection_error(),error,sizeof(error));
      response.Printf("{\"ready\":%s,\"error\":\"%s\",\"protected\":[",configs_protection_ready()?"true":"false",error);
      response.Write("\"" CONFIGS_FACTORY_NTSC "\",\"" CONFIGS_FACTORY_PAL "\"");
      unsigned count=configs_protected_count();for(unsigned i=0;i<count;i++)response.Printf(",\"%s\"",configs_protected_id(i));
      response.Write("]}");response.Finish();configs_protection_read_end();
    }
    return FALSE;
  }

  if (strcmp(target, "/api/configs/deleted") == 0) {
    if (is_post) {
      if (!HasHeader(request, "x-bmc64-web:")) {
        SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n");
        return FALSE;
      }
      char id[CONFIGS_MAX_ID_LEN+1],confirmed[4]="",permanent[4]="",legacy[4]="",restore[4]="";
      if(!webhttp::QueryParam(query,"id",id,sizeof(id)) || !IsConfigId(id) ||
         configs_is_factory(id) || !webhttp::QueryParam(query,"confirmed",confirmed,sizeof(confirmed)) || strcmp(confirmed,"1") ||
         !webhttp::QueryParam(query,"permanent",permanent,sizeof(permanent)) || strcmp(permanent,"1") ||
         webhttp::QueryParam(query,"restore",restore,sizeof(restore))) {
        SendText(socket,400,"Bad Request","confirmed permanent deletion required\n");return FALSE;
      }
      webhttp::QueryParam(query,"legacy",legacy,sizeof(legacy));
      unsigned serial=emu_config_logical_interrupt(id,legacy[0]=='1');
      if(!serial){SendText(socket,409,"Conflict","config operation busy\n");return FALSE;}
      char body[80];snprintf(body,sizeof(body),"{\"request_id\":%u}",serial);
      SendResponse(socket,202,"Accepted","application/json",body,strlen(body));
    } else {
      if (!configs_web_begin()) {
        SendText(socket, 409, "Conflict", "config management busy\n");
        return FALSE;
      }
      webhttp::CChunkedResponse response(socket, 200, "OK", "application/json");
      char error[256];JsonText(menu_configs_start_error(), error, sizeof(error));
      response.Printf("{\"ready\":%s,\"error\":\"%s\",\"deleted\":[",
                      configs_management_ready() ? "true" : "false", error);
      int count = configs_deleted_count();
      for (int i = 0; i < count; i++) {
        const char *id = configs_deleted_id((unsigned)i);
        char name[2*CONFIGS_MAX_NAME_LEN+1];JsonText(configs_deleted_name((unsigned)i),name,sizeof(name));
        response.Printf("%s{\"id\":\"%s\",\"name\":\"%s\"}",i?",":"",id,name);
      }
      unsigned serial;int state;char operation_id[33],operation_error[256],escaped_error[512];
      menu_configs_delete_status(&serial,&state,operation_id,sizeof(operation_id),operation_error,sizeof(operation_error));
      JsonText(operation_error,escaped_error,sizeof(escaped_error));
      response.Printf("],\"operation\":{\"request_id\":%u,\"state\":%d,\"id\":\"%s\",\"error\":\"%s\"}}",serial,state,operation_id,escaped_error);response.Finish();
      configs_web_end();
    }
    return FALSE;
  }

  if (is_post && strcmp(target, "/api/configs/start") == 0) {
    // Restarts BMC64 into another config, so it gets the same cross-site
    // protection as /api/fs/save.
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden", "missing X-BMC64-Web header\n");
      return FALSE;
    }
    char id[CONFIGS_MAX_ID_LEN + 1];
    char once[4] = "";
    if (!webhttp::QueryParam(query, "id", id, sizeof(id)) || !IsConfigId(id)) {
      SendText(socket, 400, "Bad Request", "bad config id\n");
      return FALSE;
    }
    webhttp::QueryParam(query, "once", once, sizeof(once));
    // Queued for the emulator main loop, which switches machine if needed
    // and restarts, or sets the error /api/status reports.
    menu_configs_clear_start_error();
    if(!emu_config_start_interrupt(id, once[0] == '1')){SendText(socket,409,"Conflict","config operation busy\n");return FALSE;}
    const char *ok = "{\"ok\":true}";
    SendResponse(socket, 202, "Accepted", "application/json", ok,
                 (unsigned) strlen(ok));
    CLogger::Get()->Write(WEBUI_LOG, LogNotice,
                          "Config %s requested via web UI", id);
    return FALSE;
  }

  if (is_post &&
      (strcmp(target, "/api/reset") == 0 ||
       strcmp(target, "/api/reset/soft") == 0 ||
       strcmp(target, "/api/warp/toggle") == 0 ||
       strcmp(target, "/api/joysticks/swap") == 0)) {
    if (!HasHeader(request, "x-bmc64-web:")) {
      SendText(socket, 403, "Forbidden",
               "missing X-BMC64-Web header\\n");
      return FALSE;
    }

    int command = WEBUI_QUICKFUNC_RESET_HARD;
    const char *action = "Hard reset";

    if (strcmp(target, "/api/reset/soft") == 0) {
      command = WEBUI_QUICKFUNC_RESET_SOFT;
      action = "Soft reset";
    } else if (strcmp(target, "/api/warp/toggle") == 0) {
      command = WEBUI_QUICKFUNC_WARP;
      action = "Warp toggle";
    } else if (strcmp(target, "/api/joysticks/swap") == 0) {
      command = WEBUI_QUICKFUNC_SWAP_PORTS;
      action = "Swap joysticks";
    }
    // Queued for the emulator main loop; BMC64 itself keeps running.
    emu_quick_func_interrupt(command);
    const char *ok = "{\"ok\":true}";
    SendResponse(socket, 202, "Accepted", "application/json", ok,
                 (unsigned) strlen(ok));
    CLogger::Get()->Write(WEBUI_LOG, LogNotice,
                          "%s requested via web UI", action);
    return FALSE;
  }

  if (is_get) {
    const struct webui_asset *asset = FindAsset(target);
    if (asset != 0) {
      SendResponse(socket, 200, "OK", asset->content_type, asset->data,
                   asset->length);
      return FALSE;
    }
  }

  if (!is_get && !is_post) {
    SendText(socket, 405, "Method Not Allowed", "method not allowed\n");
    return FALSE;
  }

  SendText(socket, 404, "Not Found", "not found\n");
  return FALSE;
}

class CWebUiTask : public CTask {
public:
  explicit CWebUiTask(CNetSubSystem *network)
      : CTask(WEBUI_TASK_STACK), m_network(network) {
    SetName("webui");
  }

  void Run(void) override {
    while (!m_network->IsRunning()) {
      CScheduler::Get()->Sleep(1);
    }

    CSocket listener(m_network, IPPROTO_TCP);
    u16 port = WEBUI_PORT;
    if (listener.Bind(port) < 0) {
      port = WEBUI_ALT_PORT;
      if (listener.Bind(port) < 0) {
        CLogger::Get()->Write(WEBUI_LOG, LogError,
                              "Cannot bind port %u or %u", (unsigned) WEBUI_PORT,
                              (unsigned) WEBUI_ALT_PORT);
        return;
      }
    }

    if (listener.Listen(WEBUI_LISTEN_BACKLOG) < 0) {
      CLogger::Get()->Write(WEBUI_LOG, LogError, "Cannot listen on port %u",
                            (unsigned) port);
      return;
    }

    CLogger::Get()->Write(WEBUI_LOG, LogNotice,
                          "Web UI listening on port %u", (unsigned) port);

    for (;;) {
      CIPAddress client_ip;
      u16 client_port;
      CSocket *connection = listener.Accept(&client_ip, &client_port);
      if (connection == 0) {
        CScheduler::Get()->MsSleep(50);
        continue;
      }
      HandleConnection(connection);
      delete connection;
      if (g_webui_stop) {
        break;
      }
      CScheduler::Get()->Yield();
    }

    // listener goes out of scope here, freeing the port.
    CLogger::Get()->Write(WEBUI_LOG, LogNotice, "Web UI stopped");
    s_started = FALSE;
  }

private:
  CNetSubSystem *m_network;
};

}  // namespace

void WebUiStart(CNetSubSystem *network, const char *pin) {
  if (s_started || network == 0) {
    return;
  }
  s_started = TRUE;
  s_pin[0] = '\0';
  if (pin != 0) {
    strncpy(s_pin, pin, sizeof(s_pin) - 1);
    s_pin[sizeof(s_pin) - 1] = '\0';
  }
  new CWebUiTask(network);  // registers itself with the scheduler
}

#else  // no Circle networking on this machine build

void WebUiStart(CNetSubSystem *, const char *) {}

#endif
