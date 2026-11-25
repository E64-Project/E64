// Bounded metadata only: at most 6000 entries (<6 MB), 24 levels, 560-byte
// paths. File contents always use the shared 32 KB buffer. FatFs has no symlinks.
// FAT's OEM case aliases must not bypass self/descendant checks.
unsigned TreeFold(unsigned char c) {
  if (c >= 'a' && c <= 'z') return c - 32;
  switch (c) {
    case 129: return 154;
    case 130: return 144;
    case 131: return 182;
    case 132: return 142;
    case 133: return 183;
    case 134: return 143;
    case 135: return 128;
    case 136: return 210;
    case 137: return 211;
    case 138: return 212;
    case 139: return 216;
    case 140: return 215;
    case 141: return 222;
    case 145: return 146;
    case 147: return 226;
    case 148: return 153;
    case 149: return 227;
    case 150: return 234;
    case 151: return 235;
    case 155: return 157;
    case 160: return 181;
    case 161: return 214;
    case 162: return 224;
    case 163: return 233;
    case 164: return 165;
    case 198: return 199;
    case 208: return 209;
    case 213: return 73;
    case 228: return 229;
    case 231: return 232;
    case 236: return 237;
    default: return c;
  }
}
bool TreeContains(const char *parent, const char *path) {
  unsigned n = 0;
  for (; parent[n]; ++n) if (!path[n] || TreeFold(parent[n]) != TreeFold(path[n])) return false;
  return !path[n] || path[n] == '/';
}

struct TreeEntry {
  TreeEntry *next, *prev;
  char relative[560];
  sd_info info;
  uint32_t crc, offset;
  unsigned depth;
};
struct TreeManifest {
  TreeEntry *head, *tail;
  unsigned count;
  TreeManifest() : head(0), tail(0), count(0) {}
  ~TreeManifest() { while (head) { TreeEntry *p = head; head = head->next; free(p); } }
  bool add(const char *relative, const sd_info &info, unsigned depth) {
    if (count >= WEBUI_FS_MAX_ENTRIES || depth > 24 || strlen(relative) >= 560) return false;
    TreeEntry *p = (TreeEntry *)calloc(1, sizeof(TreeEntry));
    if (!p) return false;
    strcpy(p->relative, relative); p->info = info; p->depth = depth; p->prev = tail;
    if (tail) tail->next = p; else head = p;
    tail = p; ++count; return true;
  }
 private:
  TreeManifest(const TreeManifest &);
  TreeManifest &operator=(const TreeManifest &);
};
bool TreePath(char *out, unsigned size, const char *root, const char *relative) {
  return (unsigned)snprintf(out, size, "%s%s%s", root, *root && *relative ? "/" : "", relative) < size;
}
bool TreeAllowed(const char *path, bool writing, bool moving) {
  return configs_path_allowed(path) && configs_protection_external_allowed(path, writing) &&
      !IsProtectedPath(path) && (!moving || (!configs_path_is_managed(path) &&
      configs_protection_can_remove(path) && !emux_storage_path_busy(path)));
}
struct TreeScan {
  TreeManifest *tree;
  const char *root;
  TreeEntry *parent;
  bool moving, skipProtected, ok;
};
int TreeChild(void *ctx, const sd_info *info) {
  TreeScan *s = (TreeScan *)ctx;
  // Names come from FatFs, but validate each component before joining it.
  char relative[560], path[560], normal[560];
  const char *name = info->name;
  if (!*name || strchr(name, '/') || strchr(name, '\\') || strchr(name, ':') ||
      !strcmp(name, ".") || !strcmp(name, "..") ||
      !TreePath(relative, sizeof(relative), s->parent->relative, name) ||
      !TreePath(path, sizeof(path), s->root, relative[0] == '/' ? relative + 1 : relative) ||
      SanitizeRelPath(RelPath(path), normal, sizeof(normal)) || strcmp(normal, RelPath(path))) {
    s->ok = false; return 1;
  }
  // TreePath on the empty relative root produces the bare child name.
  if (!TreeAllowed(path, false, s->moving)) {
    if (s->skipProtected) return 0;
    s->ok = false; return 1;
  }
  s->ok = s->tree->add(relative, *info, s->parent->depth + 1);
  return s->ok ? 0 : 1;
}
bool ScanTree(TreeManifest &tree, const char *src, bool moving, bool skipProtected) {
  sd_info root;
  if (!TreeAllowed(src, false, moving) || sd_stat_info(src, &root) != SD_OK || !tree.add("", root, 0)) return false;
  for (TreeEntry *p = tree.head; p; p = p->next) {
    if (!p->info.is_dir) continue;
    char path[560]; if (!TreePath(path, sizeof(path), src, p->relative)) return false;
    TreeScan scan = { &tree, src, p, moving, skipProtected, true };
    if (sd_list_info(path, TreeChild, &scan) != SD_OK || !scan.ok) return false;
    CScheduler::Get()->Yield();
  }
  return true;
}
uint32_t TreeCrc(uint32_t crc, const unsigned char *data, unsigned len) {
  while (len--) {
    crc ^= *data++;
    for (unsigned b = 0; b < 8; ++b) crc = (crc >> 1) ^ (0xEDB88320U & (0U - (crc & 1)));
  }
  return crc;
}
// Read back every completed file. Size alone cannot detect a failed/corrupt write.
bool TreeRead(const char *path, uint32_t expected, uint32_t *crc) {
  sd_file *f = sd_open(path, SD_READ); if (!f) return false;
  uint32_t total = 0, value = ~0U; bool ok = sd_size(f) == expected;
  while (ok) {
    unsigned got = 0;
    if (sd_read(f, s_io_buffer, sizeof(s_io_buffer), &got) != SD_OK) { ok = false; break; }
    if (!got) break;
    if (got > expected - total) { ok = false; break; }
    total += got; value = TreeCrc(value, s_io_buffer, got);
    CScheduler::Get()->Yield();
  }
  if (sd_close(f) != SD_OK) ok = false;
  *crc = ~value; return ok && total == expected;
}
bool TreeCopyFile(const char *src, const char *dest, TreeEntry *entry) {
  sd_file *in = sd_open(src, SD_READ); if (!in) return false;
  sd_file *out = sd_open(dest, SD_WRITE);
  if (!out) { sd_close(in); return false; }
  uint32_t total = 0, crc = ~0U; bool ok = sd_size(in) == entry->info.size;
  while (ok) {
    unsigned got = 0;
    if (sd_read(in, s_io_buffer, sizeof(s_io_buffer), &got) != SD_OK) { ok = false; break; }
    if (!got) break;
    if (got > entry->info.size - total || sd_write(out, s_io_buffer, got) != SD_OK) { ok = false; break; }
    total += got; crc = TreeCrc(crc, s_io_buffer, got);
    CScheduler::Get()->Yield();
  }
  if (sd_close(out) != SD_OK) ok = false;
  if (sd_close(in) != SD_OK) ok = false;
  entry->crc = ~crc;
  uint32_t readback = 0;
  return ok && total == entry->info.size && TreeRead(dest, total, &readback) && readback == entry->crc;
}
bool TreeVerify(TreeManifest &tree, const char *root) {
  for (TreeEntry *p = tree.head; p; p = p->next) {
    char path[576]; sd_info info; uint32_t crc;
    if (!TreePath(path, sizeof(path), root, p->relative) || sd_stat_info(path, &info) != SD_OK ||
        info.is_dir != p->info.is_dir || (!info.is_dir &&
        (info.size != p->info.size || !TreeRead(path, info.size, &crc) || crc != p->crc))) return false;
  }
  return true;
}
// Delete only entries in the verified manifest, children first. New files cause
// nonempty-directory failure; they are never recursively removed by this move.
bool TreeRemove(TreeManifest &tree, const char *root) {
  for (TreeEntry *p = tree.tail; p; p = p->prev) {
    char path[576];
    if (!TreePath(path, sizeof(path), root, p->relative) ||
        !TreeAllowed(path, true, true) || sd_unlink(path) != SD_OK) return false;
    CScheduler::Get()->Yield();
  }
  return true;
}

// ZIP STORE. CRCs and classic-ZIP bounds are checked before HTTP headers.
// Only the entry metadata is retained, never file or archive bodies.
unsigned ZipUtf8(char *out, unsigned size, const char *oem) {
  unsigned n = 0;
  for (const unsigned char *p = (const unsigned char *)oem; *p; ++p) {
    unsigned cp = *p < 128 ? *p : kCp850High[*p - 128];
    unsigned need = cp < 128 ? 1 : cp < 2048 ? 2 : 3;
    if (n + need >= size) return 0;
    if (need == 3) out[n++] = (char)(0xe0 | (cp >> 12));
    if (need >= 2) out[n++] = (char)((need == 2 ? 0xc0 : 0x80) | ((cp >> 6) & (need == 2 ? 31 : 63)));
    out[n++] = (char)(need == 1 ? cp : 0x80 | (cp & 63));
  }
  out[n] = 0; return n;
}
unsigned ZipName(char *out, unsigned size, const char *base, TreeEntry *entry) {
  char oem[824];
  if ((unsigned)snprintf(oem, sizeof(oem), "%s%s%s%s", base, *entry->relative ? "/" : "",
      entry->relative, entry->info.is_dir ? "/" : "") >= sizeof(oem)) return 0;
  return ZipUtf8(out, size, oem);
}
void Zip16(unsigned char *p, unsigned v) { p[0] = v; p[1] = v >> 8; }
void Zip32(unsigned char *p, uint32_t v) { Zip16(p, v); Zip16(p + 2, v >> 16); }
bool ZipRecord(CSocket *socket, TreeEntry *entry, const char *name, bool central) {
  unsigned char h[46] = {}; unsigned len = strlen(name), size = entry->info.is_dir ? 0 : entry->info.size;
  Zip32(h, central ? 0x02014b50 : 0x04034b50);
  unsigned char *p = h + (central ? 6 : 4);
  if (central) Zip16(h + 4, 20);
  Zip16(p, 20); Zip16(p + 2, 0x800); // UTF-8, STORE, no data descriptor
  const sd_time &t = entry->info.mtime;
  Zip16(p + 6, (t.hour << 11) | (t.minute << 5) | (t.second / 2));
  Zip16(p + 8, ((t.year >= 1980 ? t.year - 1980 : 0) << 9) | ((t.month ? t.month : 1) << 5) | (t.day ? t.day : 1));
  Zip32(p + 10, entry->crc); Zip32(p + 14, size); Zip32(p + 18, size); Zip16(p + 22, len);
  if (central) { Zip32(h + 38, entry->info.is_dir ? 0x10 : 0); Zip32(h + 42, entry->offset); }
  return webhttp::SendAll(socket, h, central ? 46 : 30) && webhttp::SendAll(socket, name, len);
}
