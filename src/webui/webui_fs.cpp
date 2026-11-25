//
// webui_fs.cpp
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

#include "webui_fs.h"
#include "web_datasette.h"
#include "webui.h"

#if BMC64_WEBUI

#include "webui_http.h"
#include "webui_machine.h"

#include <circle/net/socket.h>
#include <circle/sched/scheduler.h>
#include <circle/types.h>

#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include "../../third_party/common/raw_cartridge.h"

#include "../sdcard/sd_fs.h"
#include "../configs/configs.h"

// Implemented in src/vice_network.cpp.
// Queues a file for the emulator main loop to autostart (interrupt safe;
// see third_party/common/ui.c).
extern "C" int emux_storage_path_busy(const char *path);
extern "C" void emu_autostart_interrupt(const char *path);
extern "C" void emu_mount_disk_interrupt(const char *path, unsigned unit);
extern "C" void emu_load_prg_interrupt(const char *path);
extern "C" unsigned emu_raw_cartridge_submit(const char *path, int type, int replace);
extern "C" int emu_raw_cartridge_status(unsigned id, char *error, unsigned size);

using webhttp::CChunkedResponse;

namespace {

class ConfigRequestLease {
 public:
  explicit ConfigRequestLease(CSocket *socket) : held(configs_web_begin()) {
    if (!held) webhttp::SendText(socket, 409, "Conflict", "config management busy; retry\n");
  }
  ~ConfigRequestLease() { if (held) configs_web_end(); }
  bool acquired() const { return held; }
 private:
  bool held;
  ConfigRequestLease(const ConfigRequestLease &);
  ConfigRequestLease &operator=(const ConfigRequestLease &);
};

const unsigned WEBUI_FS_MAX_ENTRIES = 6000;
const unsigned WEBUI_FS_IO_CHUNK = 32 * 1024;
// Largest file the editor will open or save (the config files are a few KB;
// the body is streamed to a temp file, so this is not a RAM limit).
const unsigned WEBUI_FS_EDIT_MAX = 256 * 1024;

/* Enhanced C64 build: the Web UI manages the permanent internal
   USB1 data drive. */
const char *const WEBUI_DATA_VOLUME = "USB";

const char *RelPath(const char *path) {
  const char *colon = strchr(path, ':');
  return colon != NULL ? colon + 1 : path;
}

const char *PathVolume(const char *path) {
  if (strncmp(path, "SD:", 3) == 0) {
    return "SD";
  }
  if (strncmp(path, "USB2:", 5) == 0) return "USB2";
  if (strncmp(path, "USB3:", 5) == 0) return "USB3";
  return "USB";
}

boolean AllowedVolume(const char *vol) {
  return strcmp(vol, "USB") == 0 || strcmp(vol, "USB1") == 0 ||
         strcmp(vol, "USB2") == 0 || strcmp(vol, "USB3") == 0 ||
         strcmp(vol, "SD") == 0;
}

const char *FatVolume(const char *vol) {
  return strcmp(vol, "USB1") == 0 ? "USB" : vol;
}

// One request is handled at a time by the web UI task, so a single file
// scratch buffer is safe and keeps it off the task stack.
u8 s_io_buffer[WEBUI_FS_IO_CHUNK];

// CP850 (the FatFs OEM code page in this build) 0x80..0xFF -> Unicode.
const unsigned short kCp850High[128] = {
    0x00C7, 0x00FC, 0x00E9, 0x00E2, 0x00E4, 0x00E0, 0x00E5, 0x00E7,
    0x00EA, 0x00EB, 0x00E8, 0x00EF, 0x00EE, 0x00EC, 0x00C4, 0x00C5,
    0x00C9, 0x00E6, 0x00C6, 0x00F4, 0x00F6, 0x00F2, 0x00FB, 0x00F9,
    0x00FF, 0x00D6, 0x00DC, 0x00F8, 0x00A3, 0x00D8, 0x00D7, 0x0192,
    0x00E1, 0x00ED, 0x00F3, 0x00FA, 0x00F1, 0x00D1, 0x00AA, 0x00BA,
    0x00BF, 0x00AE, 0x00AC, 0x00BD, 0x00BC, 0x00A1, 0x00AB, 0x00BB,
    0x2591, 0x2592, 0x2593, 0x2502, 0x2524, 0x00C1, 0x00C2, 0x00C0,
    0x00A9, 0x2563, 0x2551, 0x2557, 0x255D, 0x00A2, 0x00A5, 0x2510,
    0x2514, 0x2534, 0x252C, 0x251C, 0x2500, 0x253C, 0x00E3, 0x00C3,
    0x255A, 0x2554, 0x2569, 0x2566, 0x2560, 0x2550, 0x256C, 0x00A4,
    0x00F0, 0x00D0, 0x00CA, 0x00CB, 0x00C8, 0x0131, 0x00CD, 0x00CE,
    0x00CF, 0x2518, 0x250C, 0x2588, 0x2584, 0x00A6, 0x00CC, 0x2580,
    0x00D3, 0x00DF, 0x00D4, 0x00D2, 0x00F5, 0x00D5, 0x00B5, 0x00FE,
    0x00DE, 0x00DA, 0x00DB, 0x00D9, 0x00FD, 0x00DD, 0x00AF, 0x00B4,
    0x00AD, 0x00B1, 0x2017, 0x00BE, 0x00B6, 0x00A7, 0x00F7, 0x00B8,
    0x00B0, 0x00A8, 0x00B7, 0x00B9, 0x00B3, 0x00B2, 0x25A0, 0x00A0,
};

void EmitUtf8(CChunkedResponse *r, unsigned cp) {
  char out[3];
  if (cp < 0x80) {
    out[0] = (char) cp;
    r->WriteN(out, 1);
  } else if (cp < 0x800) {
    out[0] = (char) (0xC0 | (cp >> 6));
    out[1] = (char) (0x80 | (cp & 0x3F));
    r->WriteN(out, 2);
  } else {
    out[0] = (char) (0xE0 | (cp >> 12));
    out[1] = (char) (0x80 | ((cp >> 6) & 0x3F));
    out[2] = (char) (0x80 | (cp & 0x3F));
    r->WriteN(out, 3);
  }
}

// Write s as a JSON string literal (with surrounding quotes), escaping
// control characters and translating the OEM high range to UTF-8.
void JsonString(CChunkedResponse *r, const char *s) {
  r->Write("\"");
  for (const unsigned char *p = (const unsigned char *) s; *p != '\0'; p++) {
    unsigned char c = *p;
    if (c == '"' || c == '\\') {
      char esc[2] = {'\\', (char) c};
      r->WriteN(esc, 2);
    } else if (c == '\n') {
      r->Write("\\n");
    } else if (c == '\r') {
      r->Write("\\r");
    } else if (c == '\t') {
      r->Write("\\t");
    } else if (c < 0x20) {
      r->Printf("\\u%04x", c);
    } else if (c < 0x80) {
      char ch = (char) c;
      r->WriteN(&ch, 1);
    } else {
      EmitUtf8(r, kCp850High[c - 0x80]);
    }
  }
  r->Write("\"");
}

void WriteDateTime(CChunkedResponse *r, const sd_time *t) {
  if (t->year == 0) {
    return;  // unknown timestamp -> empty string
  }
  r->Printf("%04u-%02u-%02uT%02u:%02u:%02u", t->year, t->month, t->day,
            t->hour, t->minute, t->second);
}

// Parse "YYYY-MM-DDTHH:MM:SS" (local wall-clock time, as WriteDateTime
// emits). Returns FALSE if malformed or outside what FAT can store
// (1980..2107).
boolean ParseDateTime(const char *s, sd_time *t) {
  unsigned year, month, day, hour, minute, second;
  if (sscanf(s, "%4u-%2u-%2uT%2u:%2u:%2u", &year, &month, &day, &hour, &minute,
             &second) != 6) {
    return FALSE;
  }
  if (year < 1980 || year > 2107 || month < 1 || month > 12 || day < 1 ||
      day > 31 || hour > 23 || minute > 59 || second > 59) {
    return FALSE;
  }
  t->year = (uint16_t) year;
  t->month = (uint8_t) month;
  t->day = (uint8_t) day;
  t->hour = (uint8_t) hour;
  t->minute = (uint8_t) minute;
  t->second = (uint8_t) second;
  return TRUE;
}

// Normalise a client path into a sandboxed absolute path within a volume.
// Returns 0 on success (out starts with '/'), -1 if the path is unsafe.
int SanitizeRelPath(const char *in, char *out, unsigned out_size) {
  if (out_size < 2) {
    return -1;
  }
  if (in == 0 || in[0] == '\0') {
    strcpy(out, "/");
    return 0;
  }
  if (in[0] != '/') {
    return -1;
  }

  unsigned o = 1;
  out[0] = '/';
  const char *p = in;
  while (*p != '\0') {
    while (*p == '/') {
      p++;
    }
    const char *seg = p;
    while (*p != '\0' && *p != '/') {
      p++;
    }
    unsigned seg_len = (unsigned) (p - seg);
    if (seg_len == 0) {
      continue;
    }
    if (seg_len > SD_MAX_NAME_LEN) {
      return -1;
    }
    if (seg_len == 1 && seg[0] == '.') {
      continue;
    }
    if (seg_len == 2 && seg[0] == '.' && seg[1] == '.') {
      return -1;
    }
    // FAT trims trailing dots/spaces; reject aliases before safety comparisons.
    if (seg[seg_len - 1] == '.' || seg[seg_len - 1] == ' ') return -1;
    for (unsigned i = 0; i < seg_len; i++) {
      unsigned char c = (unsigned char) seg[i];
      if (c < 0x20 || c == '\\' || c == ':' || c == '*' || c == '?' ||
          c == '"' || c == '<' || c == '>' || c == '|') {
        return -1;
      }
    }
    if (o > 1) {
      if (o + 1 >= out_size) {
        return -1;
      }
      out[o++] = '/';
    }
    if (o + seg_len >= out_size) {
      return -1;
    }
    memcpy(out + o, seg, seg_len);
    o += seg_len;
  }
  out[o] = '\0';
  return 0;
}

// Resolve and validate the vol/path query parameters. Returns 0 on
// success and fills clean, a path on the card for sd_fs.h; on failure it has
// already sent an error response and returns -1.
int ResolveTarget(CSocket *socket, const char *query, char *clean,
                  unsigned clean_size, boolean require_file) {
  char vol[24];
  char raw[560];
  char rel[560];

  /* USB1 is the default data volume, but the SD card remains accessible
     for settings, configs and other system configuration files. */
  if (!webhttp::QueryParam(query, "vol", vol, sizeof(vol)) ||
      vol[0] == '\0') {
    strcpy(vol, WEBUI_DATA_VOLUME);
  }

  if (!AllowedVolume(vol)) {
    webhttp::SendText(socket, 404, "Not Found", "unknown volume\n");
    return -1;
  }

  if (!webhttp::QueryParam(query, "path", raw, sizeof(raw))) {
    if (query != 0 &&
        (strncmp(query, "path=", 5) == 0 ||
         strstr(query, "&path=") != 0)) {
      webhttp::SendText(socket, 400, "Bad Request",
                        "path too long or invalid\n");
      return -1;
    }
    strcpy(raw, "/");
  }

  if (SanitizeRelPath(raw, rel, sizeof(rel)) != 0) {
    webhttp::SendText(socket, 400, "Bad Request", "bad path\n");
    return -1;
  }

  if (require_file && strcmp(rel, "/") == 0) {
    webhttp::SendText(socket, 400, "Bad Request", "not a file\n");
    return -1;
  }

  int n = snprintf(clean, clean_size, "%s:%s", FatVolume(vol), rel);
  if (n <= 0 || (unsigned)n >= clean_size) {
    webhttp::SendText(socket, 400, "Bad Request", "path too long\n");
    return -1;
  }

  if (!configs_path_allowed(clean) || !configs_protection_external_allowed(clean, 0)) {
    webhttp::SendText(socket, 403, "Forbidden", "config deleted or management records unavailable\n");
    return -1;
  }
  return 0;
}

boolean CiEqual(const char *a, const char *b) {
  for (; *a != '\0' && *b != '\0'; a++, b++) {
    char ca = *a;
    char cb = *b;
    if (ca >= 'A' && ca <= 'Z') ca = (char) (ca + 32);
    if (cb >= 'A' && cb <= 'Z') cb = (char) (cb + 32);
    if (ca != cb) return FALSE;
  }
  return *a == *b;
}

// Only the image/program types this machine's Autostart accepts as-is
// (webui_machine.cpp).
boolean IsAutostartable(const char *clean) {
  const char *dot = 0;
  for (const char *p = clean; *p != '\0'; p++) {
    if (*p == '/') dot = 0;
    else if (*p == '.') dot = p + 1;
  }
  return dot != 0 && WebUiMachineCanRun(dot);
}

// BMC64's own configuration files. Upload and delete refuse them (in any
// folder); the editor's save endpoint is the only way the web UI changes them.
const char *const kConfigFiles[] = {
    "settings.txt",
    "wpa_supplicant.conf", "wifi-settings.conf", "network.cfg",
    "cmdline.txt", "config.txt",
    "machines.txt",
};

boolean IsConfigFile(const char *name) {
  for (unsigned i = 0; i < sizeof(kConfigFiles) / sizeof(kConfigFiles[0]); i++) {
    if (CiEqual(name, kConfigFiles[i])) return TRUE;
  }
  return FALSE;
}

// vice.ini is editable too, but (unlike the files above) stays uploadable so
// a prepared copy can still be dropped on the card.
boolean IsEditableName(const char *name) {
  return IsConfigFile(name) || CiEqual(name, "vice.ini");
}

// Keyboard mapping files are plain text that lives in the machine folders
// (C64/rpi_pos.vkm, ...), so they are editable wherever they are on the card.
boolean IsKeymapName(const char *name) {
  size_t length = strlen(name);
  return length > 4 && CiEqual(name + length - 4, ".vkm");
}

// Starts with "/configs/" (any case); returns the rest, or 0.
const char *InConfigsFolder(const char *clean) {
  clean = RelPath(clean);
  static const char kConfigs[] = "/configs/";
  const unsigned length = sizeof(kConfigs) - 1;
  if (strlen(clean) <= length) return 0;
  char start[sizeof(kConfigs)];
  memcpy(start, clean, length);
  start[length] = '\0';
  return CiEqual(start, kConfigs) ? clean + length : 0;
}

// Config files (docs/CONFIGS.md, Config files): active.txt in /configs,
// each config's config.txt, settings files (settings.txt in older ones,
// settings-<machine>.txt) and vice.ini.
boolean IsConfigFilePath(const char *clean) {
  const char *rest = InConfigsFolder(clean);
  if (rest == 0) return FALSE;
  const char *slash = strchr(rest, '/');
  if (slash == 0) {
    return CiEqual(rest, "active.txt");
  }
  const char *name = slash + 1;
  if (*name == '\0' || strchr(name, '/') != 0) return FALSE;  // one level only
  unsigned folder_length = (unsigned) (slash - rest);
  if (folder_length == 0 || folder_length > SD_MAX_NAME_LEN) return FALSE;
  // settings.txt, or settings-<machine>.txt
  size_t length = strlen(name);
  boolean settings = FALSE;
  if (length >= 12 && CiEqual(name + length - 4, ".txt")) {
    char start[9];
    memcpy(start, name, 8);
    start[8] = '\0';
    settings = CiEqual(start, "settings") &&
               (length == 12 || name[8] == '-');
  }
  return CiEqual(name, "config.txt") || settings || CiEqual(name, "vice.ini");
}

// The config files are editable only in the volume root; keymaps anywhere;
// config files in /configs.
boolean IsProtectedPath(const char *clean);

boolean IsEditablePath(const char *clean) {
  if (!configs_protection_external_allowed(clean, 1)) return FALSE;
  clean = RelPath(clean);
  if (clean[0] != '/') return FALSE;
  const char *base = strrchr(clean, '/') + 1;
  size_t length = strlen(base);
  boolean text = length >= 4 && CiEqual(base + length - 4, ".txt");
  return IsKeymapName(base) || (base == clean + 1 && IsEditableName(base)) ||
         IsConfigFilePath(clean) || (text && !IsProtectedPath(clean));
}

// Uploads must not clobber BMC64's own configuration or the Wi-Fi
// firmware directory.
boolean IsProtectedPath(const char *clean) {
  if (!configs_protection_external_allowed(clean, 1)) return TRUE;
  if (!configs_path_allowed(clean) || (configs_path_is_managed(clean) && CiEqual(RelPath(clean), "/configs"))) return TRUE;
  clean = RelPath(clean);
  const char *seg = clean;
  while (*seg == '/') seg++;
  const char *seg_end = seg;
  while (*seg_end != '\0' && *seg_end != '/') seg_end++;
  if ((unsigned) (seg_end - seg) == 8) {
    char first[9];
    memcpy(first, seg, 8);
    first[8] = '\0';
    if (CiEqual(first, "firmware")) return TRUE;
  }

  const char *base = clean;
  for (const char *p = clean; *p != '\0'; p++) {
    if (*p == '/') base = p + 1;
  }
  return IsConfigFile(base) || CiEqual(base, "bmc64.log");
}

// A name typed into New folder / Rename: one path segment that FAT stores
// exactly as written. Printable ASCII only, because paths reach FatFs
// unconverted (its OEM code page is CP850, and only the listing translates
// to UTF-8), so a UTF-8 name would be stored garbled. FatFs would also
// silently trim a trailing dot or space, so those are refused rather than
// creating a different name than the one asked for.
boolean IsValidEntryName(const char *name) {
  size_t length = strlen(name);
  if (length == 0 || length > SD_MAX_NAME_LEN) return FALSE;
  if (name[0] == ' ' || name[length - 1] == ' ' || name[length - 1] == '.') {
    return FALSE;
  }
  for (const char *p = name; *p != '\0'; p++) {
    unsigned char c = (unsigned char) *p;
    if (c < 0x20 || c >= 0x7F || c == '/' || c == '\\' || c == ':' ||
        c == '*' || c == '?' || c == '"' || c == '<' || c == '>' ||
        c == '|') {
      return FALSE;
    }
  }
  return TRUE;
}

const char *const kBadNameText =
    "invalid name: use plain ASCII without / \\ : * ? \" < > |, and no "
    "leading space or trailing space or dot\n";

enum BodyResult {
  BODY_OK,
  BODY_CREATE_FAILED,
  BODY_WRITE_FAILED,  // write error (disk full?)
  BODY_TRUNCATED,     // client aborted or timed out
  BODY_HAS_NUL,       // only when reject_nul is set
};

// Stream a request body into a new file at temppath: prefetched bytes (read
// with the headers) first, then the rest from the socket, `total` bytes in
// all. On anything but BODY_OK the temp file is removed.
BodyResult ReceiveBodyToFile(CSocket *socket, const char *temppath,
                             const unsigned char *prefetched,
                             unsigned prefetched_len, unsigned long total,
                             boolean reject_nul) {
  sd_file *file = sd_open(temppath, SD_WRITE);
  if (file == 0) {
    return BODY_CREATE_FAILED;
  }

  unsigned long written = 0;
  BodyResult result = BODY_OK;

  if (prefetched_len > total) {
    prefetched_len = (unsigned) total;
  }
  if (prefetched_len > 0) {
    if (reject_nul && memchr(prefetched, 0, prefetched_len) != 0) {
      result = BODY_HAS_NUL;
    } else if (sd_write(file, prefetched, prefetched_len) != SD_OK) {
      result = BODY_WRITE_FAILED;
    }
    written += prefetched_len;
  }

  while (result == BODY_OK && written < total) {
    unsigned long remain = total - written;
    unsigned want = remain < sizeof(s_io_buffer) ? (unsigned) remain
                                                 : sizeof(s_io_buffer);
    int n = socket->Receive(s_io_buffer, want, 0);
    if (n <= 0) {
      result = BODY_TRUNCATED;
      break;
    }
    if (reject_nul && memchr(s_io_buffer, 0, (unsigned) n) != 0) {
      result = BODY_HAS_NUL;
      break;
    }
    if (sd_write(file, s_io_buffer, (unsigned) n) != SD_OK) {
      result = BODY_WRITE_FAILED;
      break;
    }
    written += (unsigned) n;
    CScheduler::Get()->Yield();
  }

  if (sd_close(file) != SD_OK && result == BODY_OK) {
    result = BODY_WRITE_FAILED;
  }
  if (result != BODY_OK) {
    sd_unlink(temppath);
  }
  return result;
}

void SendBodyFailure(CSocket *socket, BodyResult result) {
  switch (result) {
  case BODY_CREATE_FAILED:
    webhttp::SendText(socket, 500, "Internal Server Error",
                      "cannot create file\n");
    break;
  case BODY_WRITE_FAILED:
    webhttp::SendText(socket, 507, "Insufficient Storage",
                      "write failed (disk full?)\n");
    break;
  case BODY_HAS_NUL:
    webhttp::SendText(socket, 400, "Bad Request", "not a text file\n");
    break;
  default:
    webhttp::SendText(socket, 400, "Bad Request", "upload truncated\n");
    break;
  }
}

// Lets other tasks run while a big folder is deleted.
void YieldWhileDeleting(void *ctx) {
  (void) ctx;
  CScheduler::Get()->Yield();
}

// ---- listing a folder ----

struct ListState {
  CChunkedResponse *r;
  const char *clean;
  boolean at_root;
  boolean first;
  boolean truncated;
  unsigned count;
};

int ListEntry(void *ctx, const sd_info *info) {
  ListState *state = (ListState *) ctx;
  CChunkedResponse *r = state->r;
  if (state->count >= WEBUI_FS_MAX_ENTRIES) {
    state->truncated = TRUE;
    return 1;
  }
  char managed_child[640];
  int managed_length = snprintf(managed_child, sizeof(managed_child), "%s%s%s",
                                state->clean, state->at_root ? "" : "/", info->name);
  if (managed_length < 0 || (unsigned)managed_length >= sizeof(managed_child) ||
      (!configs_path_allowed(managed_child) || !configs_protection_external_allowed(managed_child, 0))) return 0;
  if (!state->first) {
    r->Write(",");
  }
  state->first = FALSE;

  r->Write("{\"name\":");
  JsonString(r, info->name);
  r->Printf(",\"size\":%lu,\"dir\":%s,\"mtime\":\"",
            (unsigned long) info->size, info->is_dir ? "true" : "false");
  WriteDateTime(r, &info->mtime);
  r->Write("\"");
  char child[560];
  boolean child_ok = (unsigned) snprintf(child, sizeof(child), "%s%s%s",
                                         state->clean,
                                         state->at_root ? "" : "/",
                                         info->name) < sizeof(child);
  if (child_ok && !info->is_dir && info->size <= WEBUI_FS_EDIT_MAX &&
      IsEditablePath(child)) {
    r->Write(",\"edit\":true");
  }
  // Entries the web UI won't rename or delete, so the page can leave
  // those actions out of the row's menu.
  if (child_ok && IsProtectedPath(child)) {
    r->Write(",\"protected\":true");
  }
  r->Write("}");

  state->count++;
  if ((state->count & 63) == 0) {
    CScheduler::Get()->Yield();
  }
  return r->Failed() ? 1 : 0;
}

// Open/read/close just enough to establish directory availability. Never scan
// the allocation table for free space or explicitly remount a volume here.
int ProbeDirectory(void *ctx, const sd_info *info) {
  (void) ctx;
  (void) info;
  return 1;
}

void SendDirectoryFailure(CSocket *socket, int rc) {
  if (rc == SD_NOT_FOUND || rc == SD_INVALID) {
    webhttp::SendText(socket, 404, "Not Found", "no such directory\n");
  } else if (rc == SD_DENIED) {
    webhttp::SendText(socket, 403, "Forbidden", "directory access denied\n");
  } else {
    webhttp::SendText(socket, 503, "Service Unavailable",
                      "directory unavailable or read failed\n");
  }
}

/* Runtime Config files use the same recovery protocol as native saves.
 * Other volumes and unrelated files retain the general filesystem behavior. */
boolean SaveUserConfig(CSocket *socket, const char *query, const char *clean,
                       const unsigned char *prefetched, unsigned prefetched_len,
                       unsigned long total, boolean text, boolean overwrite) {
  if (!configs_path_is_managed(clean) || !IsConfigFilePath(clean)) return FALSE;
  const char *rest = InConfigsFolder(clean);
  const char *slash = rest ? strchr(rest, '/') : 0;
  if (!slash || slash - rest > CONFIGS_MAX_ID_LEN) return FALSE;
  char id[CONFIGS_MAX_ID_LEN + 1];
  unsigned n = (unsigned)(slash - rest);
  for (unsigned i = 0; i < n; i++) {
    char c = rest[i]; id[i] = c >= 'A' && c <= 'Z' ? c + 32 : c;
  }
  id[n] = 0;
  if (!configs_path_belongs(clean, id)) return FALSE;
  if (configs_storage_begin(id) != CONFIGS_OK) {
    webhttp::SendText(socket, 409, "Conflict", "config storage busy; retry\n");
    return TRUE;
  }
  char next[CONFIGS_MAX_PATH_LEN];
  if (configs_storage_prepare(clean, next, sizeof(next), 0) != CONFIGS_OK) {
    configs_storage_end();
    webhttp::SendText(socket, 500, "Internal Server Error", "cannot recover config file\n");
    return TRUE;
  }
  sd_info info;
  int exists = sd_stat_info(clean, &info);
  if ((exists != SD_OK && exists != SD_NOT_FOUND) ||
      (exists == SD_OK && (info.is_dir || !overwrite))) {
    configs_storage_end();
    webhttp::SendText(socket, 409, "Conflict", "cannot replace target\n");
    return TRUE;
  }
  BodyResult result = ReceiveBodyToFile(socket, next, prefetched, prefetched_len, total, text);
  if (result != BODY_OK) {
    configs_storage_end(); SendBodyFailure(socket, result); return TRUE;
  }
  int rc = text ? configs_storage_commit_backup(clean) : configs_storage_commit(clean);
  configs_storage_end();
  if (rc != CONFIGS_OK) {
    webhttp::SendText(socket, 500, "Internal Server Error", "cannot finalise config save\n");
    return TRUE;
  }
  if (!text) {
    char mtime[24]; sd_time stamp;
    if (webhttp::QueryParam(query, "mtime", mtime, sizeof(mtime)) && ParseDateTime(mtime, &stamp))
      sd_set_mtime(clean, &stamp);
  }
  char body[64];
  int size = snprintf(body, sizeof(body), "{\"ok\":true,\"size\":%lu}", total);
  webhttp::SendResponse(socket, 200, "OK", "application/json", body, size > 0 ? (unsigned)size : 0);
  return TRUE;
}

#include "webui_fs_tree.h"

}  // namespace

void WebUiFsVolumes(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char capacity[8];
  const boolean with_capacity =
      webhttp::QueryParam(query, "capacity", capacity, sizeof(capacity)) &&
      strcmp(capacity, "1") == 0;
  static const char *const ids[] = {"USB", "USB2", "USB3", "SD"};
  static const char *const paths[] = {"USB:/", "USB2:/", "USB3:/", "SD:/"};

  CChunkedResponse r(socket, 200, "OK", "application/json");
  r.Write("{\"volumes\":[");
  boolean first = TRUE;
  for (unsigned i = 0; i < 4; ++i) {
    if (sd_list_info(paths[i], ProbeDirectory, NULL) != SD_OK) continue;
    if (!first) r.Write(",");
    first = FALSE;
    r.Printf("{\"id\":\"%s\",\"kind\":\"%s\"", ids[i],
             i == 3 ? "sdcard" : "usb");
    char label[256];
    if (sd_volume_label(paths[i], label, sizeof(label)) == SD_OK && *label) {
      r.Write(",\"label\":"); JsonString(&r, label);
    }
    // Capacity is an explicit dashboard request, not part of Files Refresh.
    if (with_capacity) {
      uint32_t total = 0, available = 0;
      if (sd_space_kb_path(paths[i], &total, &available) == SD_OK) {
        r.Printf(",\"total_kb\":%lu,\"free_kb\":%lu",
                 (unsigned long) total, (unsigned long) available);
      } else {
        r.Write(",\"capacity_error\":true");
      }
    }
    r.Write("}");
  }
  r.Write("]}");
  r.Finish();
}

void WebUiFsList(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), FALSE) != 0) {
    return;
  }

  // Validate even the root before sending HTTP 200; a removable volume's
  // root does not necessarily exist. Mid-stream errors are reported in JSON.
  int rc = sd_list_info(clean, ProbeDirectory, NULL);
  if (rc != SD_OK) {
    SendDirectoryFailure(socket, rc);
    return;
  }

  CChunkedResponse r(socket, 200, "OK", "application/json");
  r.Write("{\"vol\":");
  JsonString(&r, PathVolume(clean));
  r.Write(",\"path\":");
  JsonString(&r, RelPath(clean));
  r.Write(",\"entries\":[");

  ListState state;
  state.r = &r;
  state.clean = clean;
  state.at_root = strcmp(RelPath(clean), "/") == 0;
  state.first = TRUE;
  state.truncated = FALSE;
  state.count = 0;
  rc = sd_list_info(clean, ListEntry, &state);

  r.Printf("],\"truncated\":%s", state.truncated ? "true" : "false");
  if (rc != SD_OK) {
    // Headers may already be sent. The client rejects this whole listing,
    // including partial entries, rather than displaying an empty/partial folder.
    r.Write(",\"error\":\"directory read failed\",\"error_status\":503");
  }
  r.Write("}");
  r.Finish();
}

void WebUiFsDownload(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) {
    return;
  }

  sd_file *file = sd_open(clean, SD_READ);
  if (file == 0) {
    webhttp::SendText(socket, 404, "Not Found", "cannot open file\n");
    return;
  }
  uint32_t size = sd_size(file);

  const char *base = clean;
  for (const char *p = clean; *p != '\0'; p++) {
    if (*p == '/') {
      base = p + 1;
    }
  }
  char safe_name[128];
  unsigned si = 0;
  for (const char *p = base; *p != '\0' && si + 1 < sizeof(safe_name); p++) {
    unsigned char c = (unsigned char) *p;
    if (c == '"' || c == '\\' || c < 0x20) {
      continue;
    }
    safe_name[si++] = (char) c;
  }
  safe_name[si] = '\0';
  if (si == 0) {
    strcpy(safe_name, "download");
  }

  char header[400];
  int hn = snprintf(header, sizeof(header),
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/octet-stream\r\n"
                    "Content-Length: %lu\r\n"
                    "Content-Disposition: attachment; filename=\"%s\"\r\n"
                    "Connection: close\r\n"
                    "Cache-Control: no-store\r\n"
                    "\r\n",
                    (unsigned long) size, safe_name);
  if (hn <= 0 || (unsigned) hn >= sizeof(header) ||
      !webhttp::SendAll(socket, header, (unsigned) hn)) {
    sd_close(file);
    return;
  }

  for (;;) {
    unsigned read_bytes = 0;
    if (sd_read(file, s_io_buffer, sizeof(s_io_buffer), &read_bytes) != SD_OK) {
      break;
    }
    if (read_bytes == 0) {
      break;
    }
    if (!webhttp::SendAll(socket, s_io_buffer, read_bytes)) {
      break;
    }
    CScheduler::Get()->Yield();
  }
  sd_close(file);
}

void WebUiFsUpload(CSocket *socket, const char *query,
                   const unsigned char *prefetched, unsigned prefetched_len,
                   long content_length) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) {
    return;
  }
  if (content_length < 0) {
    webhttp::SendText(socket, 411, "Length Required",
                      "Content-Length header required\n");
    return;
  }
  if (IsProtectedPath(clean)) {
    webhttp::SendText(socket, 403, "Forbidden", "that path is protected\n");
    return;
  }

  char overwrite[4];
  boolean allow_overwrite =
      webhttp::QueryParam(query, "overwrite", overwrite, sizeof(overwrite)) &&
      overwrite[0] == '1';

  if (SaveUserConfig(socket, query, clean, prefetched, prefetched_len,
                     (unsigned long)content_length, FALSE, allow_overwrite)) return;

  sd_info existing;
  if (sd_stat_info(clean, &existing) == SD_OK) {
    if (existing.is_dir) {
      webhttp::SendText(socket, 409, "Conflict", "target is a directory\n");
      return;
    }
    if (!allow_overwrite) {
      webhttp::SendText(socket, 409, "Conflict", "file exists\n");
      return;
    }
  }

  // Write to "<path>.part" and swap it into place on success, so an
  // aborted upload never leaves a truncated file.
  char temppath[576];
  if ((unsigned) snprintf(temppath, sizeof(temppath), "%s.part", clean) >=
      sizeof(temppath)) {
    webhttp::SendText(socket, 400, "Bad Request", "path too long\n");
    return;
  }

  unsigned long total = (unsigned long) content_length;
  BodyResult body_result = ReceiveBodyToFile(
      socket, temppath, prefetched, prefetched_len, total, FALSE);
  if (body_result != BODY_OK) {
    SendBodyFailure(socket, body_result);
    return;
  }

  sd_unlink(clean);  // ignore result: file may not exist
  if (sd_rename(temppath, clean) != SD_OK) {
    sd_unlink(temppath);
    webhttp::SendText(socket, 500, "Internal Server Error",
                      "cannot finalise upload\n");
    return;
  }

  // Keep the file's original modified time when the client supplies it;
  // otherwise (or if it can't be applied) the file keeps the upload time.
  char mtime[24];
  sd_time stamp;
  if (webhttp::QueryParam(query, "mtime", mtime, sizeof(mtime)) &&
      ParseDateTime(mtime, &stamp)) {
    sd_set_mtime(clean, &stamp);
  }

  char body[64];
  int bn = snprintf(body, sizeof(body), "{\"ok\":true,\"size\":%lu}", total);
  webhttp::SendResponse(socket, 200, "OK", "application/json", body,
                        bn > 0 ? (unsigned) bn : 0);
}

void WebUiFsSave(CSocket *socket, const char *query,
                 const unsigned char *prefetched, unsigned prefetched_len,
                 long content_length) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) {
    return;
  }
  if (!IsEditablePath(clean)) {
    webhttp::SendText(socket, 403, "Forbidden", "that file cannot be edited\n");
    return;
  }
  if (content_length < 0) {
    webhttp::SendText(socket, 411, "Length Required",
                      "Content-Length header required\n");
    return;
  }
  if ((unsigned long) content_length > WEBUI_FS_EDIT_MAX) {
    webhttp::SendText(socket, 413, "Payload Too Large",
                      "file too large to edit\n");
    return;
  }

  if (SaveUserConfig(socket, query, clean, prefetched, prefetched_len,
                     (unsigned long)content_length, TRUE, TRUE)) return;

  sd_info existing;
  boolean exists = sd_stat_info(clean, &existing) == SD_OK;
  if (exists && existing.is_dir) {
    webhttp::SendText(socket, 409, "Conflict", "target is a directory\n");
    return;
  }

  // A keymap can be in a nested folder, so size these for the longest
  // resolved path plus the ".part" / ".bak" suffix.
  char temppath[sizeof(clean) + 8];
  char bakpath[sizeof(clean) + 8];
  if ((unsigned) snprintf(temppath, sizeof(temppath), "%s.part", clean) >=
          sizeof(temppath) ||
      (unsigned) snprintf(bakpath, sizeof(bakpath), "%s.bak", clean) >=
          sizeof(bakpath)) {
    webhttp::SendText(socket, 400, "Bad Request", "path too long\n");
    return;
  }

  unsigned long total = (unsigned long) content_length;
  BodyResult body_result = ReceiveBodyToFile(
      socket, temppath, prefetched, prefetched_len, total, TRUE);
  if (body_result != BODY_OK) {
    SendBodyFailure(socket, body_result);
    return;
  }

  // Keep the previous version as "<name>.bak". The original is only moved
  // aside once the new one is fully written, and is put back if the final
  // rename fails, so a failed save never leaves a config file missing.
  if (exists) {
    sd_unlink(bakpath);  // ignore result: an older backup may not exist
    if (sd_rename(clean, bakpath) != SD_OK) {
      sd_unlink(temppath);
      webhttp::SendText(socket, 500, "Internal Server Error",
                        "cannot back up the existing file\n");
      return;
    }
  }
  if (sd_rename(temppath, clean) != SD_OK) {
    if (exists) {
      sd_rename(bakpath, clean);
    }
    sd_unlink(temppath);
    webhttp::SendText(socket, 500, "Internal Server Error",
                      "cannot finalise save\n");
    return;
  }

  char body[64];
  int bn = snprintf(body, sizeof(body), "{\"ok\":true,\"size\":%lu}", total);
  webhttp::SendResponse(socket, 200, "OK", "application/json", body,
                        bn > 0 ? (unsigned) bn : 0);
}

void WebUiFsDelete(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) {
    return;
  }
  if (configs_path_is_managed(clean) || IsProtectedPath(clean)) {
    webhttp::SendText(socket, 403, "Forbidden", "that path is protected\n");
    return;
  }

  // &recursive=1 deletes a folder together with its contents; without it
  // only an empty folder can be removed.
  char recursive[4];
  sd_info stat;
  if (webhttp::QueryParam(query, "recursive", recursive, sizeof(recursive)) &&
      recursive[0] == '1' && sd_stat_info(clean, &stat) == SD_OK &&
      stat.is_dir) {
    unsigned removed = 0;
    if (sd_remove_tree(clean, &removed, YieldWhileDeleting, 0) == SD_OK) {
      const char *ok = "{\"ok\":true}";
      webhttp::SendResponse(socket, 200, "OK", "application/json", ok,
                            (unsigned) strlen(ok));
      return;
    }
    char text[128];
    snprintf(text, sizeof(text),
             "could not delete everything (a file may be read-only): %u "
             "item%s removed, the rest of the folder is still there\n",
             removed, removed == 1 ? "" : "s");
    webhttp::SendText(socket, 409, "Conflict", text);
    return;
  }

  int rc = sd_unlink(clean);
  if (rc == SD_NOT_FOUND || rc == SD_INVALID) {
    webhttp::SendText(socket, 404, "Not Found", "no such file\n");
    return;
  }
  if (rc == SD_DENIED) {
    webhttp::SendText(socket, 409, "Conflict",
                      "cannot delete (directory not empty or read-only)\n");
    return;
  }
  if (rc != SD_OK) {
    webhttp::SendText(socket, 500, "Internal Server Error", "delete failed\n");
    return;
  }

  const char *ok = "{\"ok\":true}";
  webhttp::SendResponse(socket, 200, "OK", "application/json", ok,
                        (unsigned) strlen(ok));
}

// ---- new folder / rename ----

void WebUiFsMkdir(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) {
    return;
  }
  if (!IsValidEntryName(strrchr(clean, '/') + 1)) {
    webhttp::SendText(socket, 400, "Bad Request", kBadNameText);
    return;
  }
  if (IsProtectedPath(clean)) {
    webhttp::SendText(socket, 403, "Forbidden", "that path is protected\n");
    return;
  }

  if (sd_stat_info(clean, 0) == SD_OK) {
    webhttp::SendText(socket, 409, "Conflict", "already exists\n");
    return;
  }

  int rc = sd_mkdir(clean);
  if (rc == SD_EXISTS) {
    webhttp::SendText(socket, 409, "Conflict", "already exists\n");
    return;
  }
  if (rc == SD_NOT_FOUND) {
    webhttp::SendText(socket, 404, "Not Found", "parent folder not found\n");
    return;
  }
  if (rc != SD_OK) {
    webhttp::SendText(socket, 500, "Internal Server Error",
                      "cannot create folder\n");
    return;
  }

  const char *ok = "{\"ok\":true}";
  webhttp::SendResponse(socket, 200, "OK", "application/json", ok,
                        (unsigned) strlen(ok));
}

// POST /api/fs/rename?path=/dir/old&to=new: renames within the same folder,
// so `to` is a bare name, never a path.
void WebUiFsRename(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) {
    return;
  }

  char new_name[256];
  if (!webhttp::QueryParam(query, "to", new_name, sizeof(new_name)) ||
      !IsValidEntryName(new_name)) {
    webhttp::SendText(socket, 400, "Bad Request", kBadNameText);
    return;
  }

  const char *old_name = strrchr(clean, '/') + 1;
  char new_clean[560];
  if ((unsigned) snprintf(new_clean, sizeof(new_clean), "%.*s/%s",
                          (int) (old_name - 1 - clean), clean,
                          new_name) >= sizeof(new_clean)) {
    webhttp::SendText(socket, 400, "Bad Request", "path too long\n");
    return;
  }

  // Neither the source nor the new name may be a protected one (that would
  // let a rename create or replace settings.txt, or touch /firmware).
  if (configs_path_is_managed(clean) || configs_path_is_managed(new_clean) ||
      IsProtectedPath(clean) || IsProtectedPath(new_clean)) {
    webhttp::SendText(socket, 403, "Forbidden", "that path is protected\n");
    return;
  }

  if (sd_stat_info(clean, 0) != SD_OK) {
    webhttp::SendText(socket, 404, "Not Found", "no such file\n");
    return;
  }

  boolean unchanged = strcmp(old_name, new_name) == 0;
  boolean case_only = !unchanged && CiEqual(old_name, new_name);
  if (!unchanged && !case_only && sd_stat_info(new_clean, 0) == SD_OK) {
    webhttp::SendText(socket, 409, "Conflict", "already exists\n");
    return;
  }

  int rc = unchanged ? SD_OK : sd_rename(clean, new_clean);
  if (rc == SD_EXISTS) {
    webhttp::SendText(socket, 409, "Conflict", "already exists\n");
    return;
  }
  if (rc == SD_NOT_FOUND) {
    webhttp::SendText(socket, 404, "Not Found", "no such file\n");
    return;
  }
  if (rc != SD_OK) {
    webhttp::SendText(socket, 500, "Internal Server Error",
                      "rename failed\n");
    return;
  }

  const char *ok = "{\"ok\":true}";
  webhttp::SendResponse(socket, 200, "OK", "application/json", ok,
                        (unsigned) strlen(ok));
}

void WebUiFsDownloadFolder(CSocket *socket, const char *query) {
  ConfigRequestLease lease(socket); if (!lease.acquired()) return;
  char src[560]; if (ResolveTarget(socket, query, src, sizeof(src), TRUE)) return;
  TreeManifest tree;
  if (!ScanTree(tree, src, false, true) || !tree.head->info.is_dir) {
    webhttp::SendText(socket, 409, "Conflict", "folder unavailable, protected or exceeds archive limits\n"); return;
  }
  const char *base = strrchr(src, '/') + 1;
  uint64_t local = 0, central = 0;
  char name[2500], path[560];
  for (TreeEntry *p = tree.head; p; p = p->next) {
    unsigned len = ZipName(name, sizeof(name), base, p);
    if (!len || (!p->info.is_dir && (!TreePath(path, sizeof(path), src, p->relative) ||
        !TreeRead(path, p->info.size, &p->crc)))) {
      webhttp::SendText(socket, 409, "Conflict", "cannot read archive entry\n"); return;
    }
    p->offset = (uint32_t)local;
    local += 30 + len + (p->info.is_dir ? 0 : (uint64_t)p->info.size);
    central += 46 + len;
    if (local + central + 22 >= 0xffffffffULL) {
      webhttp::SendText(socket, 413, "Content Too Large", "classic ZIP limit exceeded\n"); return;
    }
  }
  char filename[800], encoded[2400], fallback[256];
  unsigned fallback_len = 0;
  for (const unsigned char *p = (const unsigned char *)base; *p && fallback_len + 1 < sizeof(fallback); ++p)
    fallback[fallback_len++] = *p >= 32 && *p < 127 ? (char)*p : '_';
  fallback[fallback_len] = 0;
  ZipUtf8(filename, sizeof(filename), base);
  unsigned at = 0;
  for (const unsigned char *p = (const unsigned char *)filename; *p; ++p) {
    snprintf(encoded + at, sizeof(encoded) - at, "%%%02X", *p); at += 3;
  }
  encoded[at] = 0;
  char header[3000];
  int n = snprintf(header, sizeof(header), "HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nContent-Length: %lu\r\nContent-Disposition: attachment; filename=\"%s.zip\"; filename*=UTF-8''%s.zip\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n", (unsigned long)(local + central + 22), fallback, encoded);
  if (n <= 0 || (unsigned)n >= sizeof(header) || !webhttp::SendAll(socket, header, n)) return;
  for (TreeEntry *p = tree.head; p; p = p->next) {
    ZipName(name, sizeof(name), base, p);
    if (!ZipRecord(socket, p, name, false)) return;
    if (p->info.is_dir) continue;
    TreePath(path, sizeof(path), src, p->relative);
    if (!TreeAllowed(path, false, false)) return;
    sd_file *f = sd_open(path, SD_READ); if (!f) return;
    uint32_t sent = 0, crc = ~0U; bool ok = sd_size(f) == p->info.size;
    while (ok && sent < p->info.size) {
      unsigned got = 0;
      unsigned want = p->info.size - sent;
      if (want > sizeof(s_io_buffer)) want = sizeof(s_io_buffer);
      if (sd_read(f, s_io_buffer, want, &got) != SD_OK || !got || got > want) { ok = false; break; }
      crc = TreeCrc(crc, s_io_buffer, got); sent += got;
      if (!webhttp::SendAll(socket, s_io_buffer, got)) { ok = false; break; }
    }
    if (sd_close(f) != SD_OK) ok = false;
    // An incomplete response deliberately has no central directory/EOCD.
    // Content-Length lets the browser detect the aborted download.
    if (!ok || sent != p->info.size || ~crc != p->crc) return;
  }
  for (TreeEntry *p = tree.head; p; p = p->next) {
    ZipName(name, sizeof(name), base, p); if (!ZipRecord(socket, p, name, true)) return;
  }
  unsigned char end[22] = {};
  Zip32(end, 0x06054b50); Zip16(end + 8, tree.count); Zip16(end + 10, tree.count);
  Zip32(end + 12, (uint32_t)central); Zip32(end + 16, (uint32_t)local);
  webhttp::SendAll(socket, end, sizeof(end));
}

void WebUiFsTransfer(CSocket *socket, const char *query) {
  ConfigRequestLease lease(socket); if (!lease.acquired()) return;
  char src[560], vol[24], raw[560], relative[560], dest[560], part[576];
  if (ResolveTarget(socket, query, src, sizeof(src), TRUE)) return;
  if (!webhttp::QueryParam(query, "dest_vol", vol, sizeof(vol)) || !AllowedVolume(vol) ||
      !webhttp::QueryParam(query, "dest_path", raw, sizeof(raw)) ||
      SanitizeRelPath(raw, relative, sizeof(relative))) {
    webhttp::SendText(socket, 400, "Bad Request", "invalid destination\n"); return;
  }
  // The volume root is a valid destination folder, never an empty filename.
  if (!strcmp(relative, "/")) snprintf(relative, sizeof(relative), "/%s", strrchr(src, '/') + 1);
  if ((unsigned)snprintf(dest, sizeof(dest), "%s:%s", FatVolume(vol), relative) >= sizeof(dest)) {
    webhttp::SendText(socket, 400, "Bad Request", "destination too long\n"); return;
  }
  char flag[4]; bool move = webhttp::QueryParam(query, "move", flag, sizeof(flag)) && flag[0] == '1';
  if (TreeContains(src, dest)) {
    webhttp::SendText(socket, 409, "Conflict", "destination is source or descendant\n"); return;
  }
  if (!TreeAllowed(dest, true, false) || !TreeAllowed(src, false, move)) {
    webhttp::SendText(socket, 403, "Forbidden", "protected or active path\n"); return;
  }
  snprintf(part, sizeof(part), "%s.part", dest);
  if (sd_stat_info(dest, 0) != SD_NOT_FOUND || sd_stat_info(part, 0) != SD_NOT_FOUND) {
    webhttp::SendText(socket, 409, "Conflict", "destination or staging path exists or is unavailable\n"); return;
  }
  // Validate root parents with opendir: FatFs f_stat does not accept volume roots.
  char parent[560]; strcpy(parent, dest); char *slash = strrchr(parent, '/');
  if (slash == strchr(parent, ':') + 1) slash[1] = 0; else *slash = 0;
  if (sd_list_info(parent, ProbeDirectory, 0) != SD_OK) {
    webhttp::SendText(socket, 409, "Conflict", "destination folder unavailable\n"); return;
  }
  TreeManifest tree;
  if (!ScanTree(tree, src, move, false)) {
    webhttp::SendText(socket, 409, "Conflict", "source unavailable, protected, active, too deep or too many entries\n"); return;
  }
  for (TreeEntry *p = tree.head; p; p = p->next) {
    char path[576];
    if (!TreePath(path, 560, dest, p->relative) || !TreeAllowed(path, true, false) ||
        !TreePath(path, sizeof(path), part, p->relative) || !TreeAllowed(path, true, false)) {
      webhttp::SendText(socket, 403, "Forbidden", "destination entry protected or too long\n"); return;
    }
  }
  if (move && !strcmp(PathVolume(src), PathVolume(dest))) {
    if (!TreeAllowed(src, false, true) || sd_rename(src, dest) != SD_OK) {
      webhttp::SendText(socket, 409, "Conflict", "move failed; source retained\n"); return;
    }
  } else {
    bool ok = true;
    for (TreeEntry *p = tree.head; p && ok; p = p->next) {
      char from[560], to[576];
      ok = TreePath(from, sizeof(from), src, p->relative) && TreePath(to, sizeof(to), part, p->relative);
      if (ok) ok = p->info.is_dir ? sd_mkdir(to) == SD_OK : TreeCopyFile(from, to, p);
      if (ok && p->info.mtime.year) sd_set_mtime(to, &p->info.mtime);
    }
    if (!ok || !TreeVerify(tree, part) || !TreeVerify(tree, src) ||
        sd_stat_info(dest, 0) != SD_NOT_FOUND || sd_rename(part, dest) != SD_OK) {
      // Staging remains for inspection/recovery. Never remove the source on failure.
      webhttp::SendText(socket, 500, "Internal Server Error", "transfer failed; source retained; staging may remain at destination .part\n"); return;
    }
    if (move && (!TreeVerify(tree, dest) || !TreeRemove(tree, src))) {
      webhttp::SendText(socket, 409, "Conflict", "destination retained; source cleanup incomplete\n"); return;
    }
  }
  webhttp::SendResponse(socket, 200, "OK", "application/json", "{\"ok\":true}", 11);
}

// ---- autostart ----

void WebUiFsAutostart(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) {
    return;
  }
  if (!IsAutostartable(clean)) {
    webhttp::SendText(socket, 400, "Bad Request",
                      "not an autostartable file type\n");
    return;
  }

  sd_info info;
  if (sd_stat_info(clean, &info) != SD_OK || info.is_dir) {
    webhttp::SendText(socket, 404, "Not Found", "no such file\n");
    return;
  }

  // ResolveTarget already returned a fully-qualified FatFs path,
  // for example "USB:/Disks/game.d64".
  emu_autostart_interrupt(clean);

  const char *ok = "{\"ok\":true}";
  webhttp::SendResponse(socket, 202, "Accepted", "application/json", ok,
                        (unsigned) strlen(ok));
}

void WebUiFsLoadTape(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) return;
  const char *dot = strrchr(clean, '.');
  if (!dot || !CiEqual(dot, ".tap")) {
    webhttp::SendText(socket, 400, "Bad Request", "not a TAP image\n"); return;
  }
  sd_info info;
  if (sd_stat_info(clean, &info) != SD_OK || info.is_dir) {
    webhttp::SendText(socket, 404, "Not Found", "no such file\n"); return;
  }
  unsigned serial = 0;
  int result = web_datasette_attach(clean, &serial);
  if (result <= 0) {
    webhttp::SendText(socket, result == -1 ? 501 : 409,
                      result == -1 ? "Not Implemented" : "Conflict",
                      result == -1 ? "Datasette unavailable\n" : "Datasette busy\n"); return;
  }
  char reply[64];
  int n = snprintf(reply, sizeof(reply), "{\"request_id\":%u}", serial);
  webhttp::SendResponse(socket, 202, "Accepted", "application/json", reply, n);
}

void WebUiFsMount(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char unit_str[8];
  unsigned unit = 8;
  if (webhttp::QueryParam(query, "unit", unit_str, sizeof(unit_str))) {
    if (unit_str[0] < '8' || unit_str[0] > '9' || unit_str[1] != '\0') {
      if (!(unit_str[0] == '1' && (unit_str[1] == '0' || unit_str[1] == '1') && unit_str[2] == '\0')) {
        webhttp::SendText(socket, 400, "Bad Request", "invalid drive unit\n"); return;
      }
    }
    unit = (unit_str[0] == '1') ? (unsigned)(10 + unit_str[1] - '0') : (unsigned)(unit_str[0] - '0');
  }
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) return;
  const char *dot = strrchr(clean, '.');
  if (!dot || !(CiEqual(dot, ".d64") ||
                CiEqual(dot, ".d71") ||
                CiEqual(dot, ".d81") ||
                CiEqual(dot, ".d82") ||
                CiEqual(dot, ".g64") ||
                CiEqual(dot, ".d1m") ||
                CiEqual(dot, ".d2m") ||
                CiEqual(dot, ".d4m") ||
                CiEqual(dot, ".dhd"))) {
    webhttp::SendText(socket, 400, "Bad Request", "not a disk image\n");
    return;
  }
  sd_info info;
  if (sd_stat_info(clean, &info) != SD_OK || info.is_dir) {
    webhttp::SendText(socket, 404, "Not Found", "no such file\n");
    return;
  }
  emu_mount_disk_interrupt(clean, unit);
  const char *ok = "{\"ok\":true}";
  webhttp::SendResponse(socket, 202, "Accepted", "application/json", ok,
                        (unsigned) strlen(ok));
}

void WebUiFsLoadPrg(CSocket *socket, const char *query) {
  ConfigRequestLease config_request(socket);
  if (!config_request.acquired()) return;
  char clean[560];
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) return;
  const char *dot = strrchr(clean, '.');
  if (!dot || !CiEqual(dot, ".prg") || !WebUiMachineCanRun("prg")) {
    webhttp::SendText(socket, 400, "Bad Request", "not a supported PRG\n");
    return;
  }
  sd_info info;
  if (sd_stat_info(clean, &info) != SD_OK || info.is_dir) {
    webhttp::SendText(socket, 404, "Not Found", "no such file\n");
    return;
  }
  emu_load_prg_interrupt(clean);
  const char *ok = "{\"ok\":true}";
  webhttp::SendResponse(socket, 202, "Accepted", "application/json", ok,
                        (unsigned) strlen(ok));
}

// Completion for this feature only: do not change existing CRT/autostart replies.
void WebUiFsRawCartridge(CSocket *socket, const char *query, bool submit) {
  if (!submit) {
    char id_text[16], error[160], body[256];
    if (!webhttp::QueryParam(query, "id", id_text, sizeof(id_text))) {
      webhttp::SendText(socket, 400, "Bad Request", "Missing Request ID"); return;
    }
    char *end; unsigned long id = strtoul(id_text, &end, 10);
    if (!*id_text || strspn(id_text, "0123456789") != strlen(id_text) ||
        *end || !id || id > 0xffffffffUL) {
      webhttp::SendText(socket, 400, "Bad Request", "Invalid Request ID"); return;
    }
    int state = emu_raw_cartridge_status((unsigned)id, error, sizeof(error));
    if (!state) { webhttp::SendText(socket, 409, "Conflict", "Request No Longer Available"); return; }
    // Error strings are fixed emulator messages, never file/user text.
    snprintf(body, sizeof(body), "{\"request_id\":%lu,\"state\":%d,\"error\":\"%s\"}", id, state, error);
    webhttp::SendResponse(socket, 200, "OK", "application/json", body, strlen(body)); return;
  }
  ConfigRequestLease lease(socket); if (!lease.acquired()) return;
  char clean[560], choice[8], replace[4];
  if (strcmp(WebUiMachineGet()->name, "C64")) {
    webhttp::SendText(socket, 400, "Bad Request", "Raw Cartridges Require C64"); return;
  }
  if (ResolveTarget(socket, query, clean, sizeof(clean), TRUE) != 0) return;
  const char *dot = strrchr(clean, '.');
  if (!dot || strcasecmp(dot, ".rom") ||
      !webhttp::QueryParam(query, "type", choice, sizeof(choice)) ||
      !webhttp::QueryParam(query, "replace", replace, sizeof(replace)) || strcmp(replace, "1")) {
    webhttp::SendText(socket, 400, "Bad Request", "Confirm A Raw Cartridge Type And Replacement"); return;
  }
  int type = !strcmp(choice, "8k") ? E64_RAW_8K : !strcmp(choice, "16k") ? E64_RAW_16K :
             !strcmp(choice, "ultimax") ? E64_RAW_ULTIMAX : 0;
  sd_info info;
  if (sd_stat_info(clean, &info) != SD_OK || info.is_dir) {
    webhttp::SendText(socket, 404, "Not Found", "No Such ROM File"); return;
  }
  if (!e64_raw_cartridge_size_valid(info.size, type)) {
    webhttp::SendText(socket, 400, "Bad Request", "File Size Does Not Match Cartridge Type"); return;
  }
  unsigned id = emu_raw_cartridge_submit(clean, type, 1);
  if (!id) { webhttp::SendText(socket, 409, "Conflict", "Raw Cartridge Operation Busy"); return; }
  char body[64];snprintf(body, sizeof(body), "{\"request_id\":%u}", id);
  webhttp::SendResponse(socket, 202, "Accepted", "application/json", body, strlen(body));
}

#endif // BMC64_WEBUI
