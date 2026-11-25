#ifndef E64_NATIVE_DIR_INFO_H
#define E64_NATIVE_DIR_INFO_H
#include <stdint.h>
#include <dirent.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Size of the regular file most recently returned by this open iterator.
   Metadata only: no filesystem call. Returns -1 for a directory, EOF, error,
   rewind, closed/unknown handle or null output; leaves errno unchanged. */
int bmc64_directory_entry_size(DIR *dir, uint32_t *size);
#ifdef __cplusplus
}
#endif
#endif
