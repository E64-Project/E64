//
// io_stats_bench.cpp
//
// Opt-in storage benchmark for the SD/FatFs performance investigation.
// Compiled to an empty object unless BMC64_IO_STATS is defined
// (./make_all.sh <board> --io-stats). See docs/BUILDING.md.
//
// This is the implementation of the circle_io_benchmark() /
// circle_io_stats_dump() entry points declared in
// third_party/common/circle.h. It is self-contained: the SD device is
// accessed through the SDK/FatFs transaction path, without raw device access.
//
// Licensed under the Apache License, Version 2.0.
//

extern "C" {
#include "../third_party/common/circle.h"
}
#include "../third_party/common/io_stats.h"

#ifdef BMC64_IO_STATS

#include <stdint.h>
#include <stdio.h>

#include <circle/timer.h>
#include "sdcard/sd_fs.h"

extern "C" {

void circle_io_stats_dump(void) { io_stats_dump("on demand"); }

// Only the SDK/FatFs benchmark is permitted during live emulation. Raw
// Seek+Read bypasses the physical transaction gate and is disabled in Stage 2A.
void circle_io_benchmark(void) {
  static uint8_t buf[131072] __attribute__((aligned(64)));
  printf("Raw benchmark disabled: filesystem transaction protection required.\n");

  // FatFs read of the largest file we can find, in a few chunk sizes.
  const char *machine_dir =
#if defined(RASPI_C64)
      "/c64";
#elif defined(RASPI_C128)
      "/c128";
#elif defined(RASPI_VIC20)
      "/vic20";
#elif defined(RASPI_PLUS4) || defined(RASPI_PLUS4EMU)
      "/plus4";
#elif defined(RASPI_PET)
      "/pet";
#else
      "";
#endif
  char rom_path[64];
  char stat_path[64];
  snprintf(rom_path, sizeof(rom_path), "%s/kernal", machine_dir);
  snprintf(stat_path, sizeof(stat_path), "%s/bootstat.txt", machine_dir);
  // Prefer a multi-MB file (the kernel image at the volume root) so the
  // throughput number is meaningful; fall back to a ROM, then bootstat.
  const char *candidates[] = {"/kernel8-32.img", rom_path, stat_path};

  static const unsigned kFatChunks[] = {1024, 32768, 131072};
  for (unsigned ci = 0; ci < sizeof(kFatChunks) / sizeof(kFatChunks[0]); ci++) {
    unsigned chunk = kFatChunks[ci];

    sd_file *fil = 0;
    const char *use = 0;
    for (unsigned i = 0; i < sizeof(candidates) / sizeof(candidates[0]) && !use;
         i++) {
      if ((fil = sd_open(candidates[i], SD_READ)) != 0) {
        use = candidates[i];
      }
    }
    if (!use) {
      printf("fatfs: no test file under '%s'\n", machine_dir);
      break;
    }

    unsigned totKiB = 0;
    unsigned t0 = CTimer::GetClockTicks();
    for (;;) {
      unsigned nread = 0;
      if (sd_read(fil, buf, chunk, &nread) != SD_OK || nread == 0) {
        break;
      }
      totKiB += nread / 1024;
    }
    unsigned totUs = CTimer::GetClockTicks() - t0;
    sd_close(fil);

    unsigned kbps = totUs ? (unsigned)((totKiB * 1000000ull) / totUs) : 0;
    printf("%-9s %8u %8s %8s %8u %9u  (%s %uKiB)\n",
           "fatfs", chunk, "-", "-", totUs, kbps, use, totKiB);
  }

  printf("==================================================\n");
}

} // extern "C"

#endif /* BMC64_IO_STATS */
