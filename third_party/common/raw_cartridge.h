#ifndef E64_RAW_CARTRIDGE_H
#define E64_RAW_CARTRIDGE_H
/* Web operation types, deliberately independent of VICE cartridge IDs. */
enum { E64_RAW_8K = 1, E64_RAW_16K = 2, E64_RAW_ULTIMAX = 3 };
/* Matches VICE util_file_load(..., UTIL_FILE_LOAD_SKIP_ADDRESS), including
   its optional two-byte prefix and generic 4K/12K mirror variants. */
static inline int e64_raw_cartridge_size_valid(unsigned size, int type) {
  unsigned payload = size - ((size & 2) ? 2 : 0);
  if (type == E64_RAW_8K) return payload == 4096 || payload == 8192;
  if (type == E64_RAW_16K) return payload == 12288 || payload == 16384;
  if (type == E64_RAW_ULTIMAX) return payload == 4096 || payload == 12288 || payload == 16384;
  return 0;
}
#endif
