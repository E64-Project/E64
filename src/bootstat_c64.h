#ifndef BOOTSTAT_C64
#define BOOTSTAT_C64

int dflt_bootStatNum = 15;

int dflt_bootStatWhat[] = {
    BOOTSTAT_WHAT_STAT,
    BOOTSTAT_WHAT_STAT,
    BOOTSTAT_WHAT_STAT,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
    BOOTSTAT_WHAT_FAIL,
};

const char *dflt_bootStatFile[] = {
    "kernal",
    "basic",
    "chargen",
    "fliplist-C64.vfl",
    "mps803",
    "mps803.vpl",
    "nl10-cbm",
    "1520.vpl",
    "/c64/dos1540",
    "/c64/dos1570",
    "/c64/dos2031",
    "/c64/dos2040",
    "/c64/dos3040",
    "/c64/dos4040",
    "/c64/dos1001",
};

int dflt_bootStatSize[] = {
    8192,
    8192,
    4096,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0
};

#endif
