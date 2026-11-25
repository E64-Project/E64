# Web Raw Cartridge Load & Run

Run from the project root:

    python3 tools/raw_cartridge_test/run_tests.py
    node tools/raw_cartridge_test/web_test.mjs

The host tests execute production adapter, emulation-thread queue, HTTP endpoint,
dialog and API polling code. They also execute the bundled VICE generic raw
readers and file-size/prefix handling. Socket, scheduler and machine-reset
interfaces are doubles. Fixtures are confined to temporary computer directories.
These tests do not execute cartridge code on a C64 CPU.

Only confirmed .rom requests use this new path. CRT generic autostart, BIN
handling, native raw-cartridge actions and all icon classification are unchanged.
The HTTP POST returns a request ID, not success. The browser polls the retained
completion; queued/running states cannot display success. Old IDs and a busy
slot are rejected. A polling timeout reports an unknown outcome, not failure or
success, because the queued operation may still complete.

Preflight checks the selected size/type combination, regular-file status and
readability of every byte, then closes the file before calling VICE's existing
cartridge_attach_image. The sole payload loading/mirroring is done by VICE.
CartridgeReset is preserved and restored, including after attachment failure;
its automatic detach/attach resets are inhibited. A successful attach requests
one hard reset, independent of the saved reset setting. A failure requests none.
If the resource setter itself fails, the operation reports the problem and does
not claim success or request a reset. The bundled CartridgeReset setter is an
infallible boolean assignment; this exceptional branch is fault-tested.

Limits:
- Size cannot identify content. A KERNAL/BASIC/drive ROM of a compatible size
  is not distinguishable reliably from a raw cartridge without additional
  detection. Opening a ROM only opens a warning/type-confirmation dialog.
  Explicitly confirming an unsuitable ROM may attach it, but will not turn it
  into a bootable cartridge. No filename/directory guessing is used.
- VICE attachment is not transactional. Preflight minimizes failures; an
  unexpected failure after detach may remove the previous cartridge. The
  dialog and late-error message disclose this; no rollback loader is added.
- No new file-writing operation is introduced. VICE's existing detach behavior
  is preserved, including any configured cartridge auto-save (for example,
  EasyFlashWriteCRT). Source ROM files are opened read-only.
- The single request slot retains its result until a subsequent request. If a
  different client replaces a completed result before polling, the old client
  receives an explicit unavailable-ID error rather than another job's success.
- Hardware testing is still required with known bootable cartridges for 8K,
  16K and Ultimax, both original CartridgeReset states, replacement transitions,
  real browser keyboard navigation and actual cartridge boot execution.
