# PRG RAM-injection regression

Run `python3 tools/prg_ram_autostart_test/run_tests.py` from the source root.
The host harness executes extracted current production functions, with in-memory
read-only PRGs and hard-failing temporary-image/directory creation spies.
It tests E64's policy at settings restoration and all shared autostart wrappers,
VICE RAM staging/injection, real C64 BASIC pointer updates, RUN versus Load Only,
source-byte integrity, Warp setting preservation, disk/tape dispatch and errors.
It never creates a disk image or modifies a source PRG or SD card.

This does not execute a C64 CPU/KERNAL. Hardware testing remains required with
standard KERNAL and JiffyDOS: native/Web PRG starts, configured startup PRG,
Warp On/Off, RUN result, disk/tape autostart, and absence of new autostart images.
Existing temporary images are deliberately not deleted. Multi-file programs
still need their original media; machine-language programs without a BASIC
startup stub may require SYS. No disk-image fallback is provided.

Failed queued requests show the existing native error dialog. The Web endpoint
continues to acknowledge a queued request asynchronously; its HTTP success does
not establish that the emulated program subsequently ran.
