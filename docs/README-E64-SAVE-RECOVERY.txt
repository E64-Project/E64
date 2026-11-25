E64 Main settings crash-recovery prototype — SOURCE REVIEW ONLY

This package is NOT ready to install on the Pi64 or copy onto the SD card.

Changes:
- Save Main's settings to /E64SET.NEW before committing.
- Keep /E64SET.NEW and /E64SET.OLD inaccessible to external writes.
- On a fully closed staged file, move /settings.txt to /E64SET.OLD,
  then promote /E64SET.NEW to /settings.txt.
- Recover /E64SET.OLD on startup if the final file is missing.
- Leave the original file unchanged if staging fails.

Validation performed:
- 8 state-machine scenarios, including simulated interruptions and rename
  failures, passed in the included Python model. This does NOT prove the
  behavior of the real FatFs implementation or hardware.

Outstanding before firmware deployment:
- Integrate production FatFs fault-injection tests for every rename failure
  and simulated interruption (not yet done).
- Verify that boot ordering runs recovery before every settings-file read.
- Audit VICE's separate vice.ini save for interruption safety.
- Complete a full compile, test pass, and hardware regression test.

Do not install or flash this prototype.
