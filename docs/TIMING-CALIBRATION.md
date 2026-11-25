# Video timing calibration

Open Video Timing Test and select **Start Calculation**. The centered
TIMING CALIBRATION CORRECTION title and separators frame the instructions.
During the existing ten-minute test, a centered CHARGEN countdown panel
replaces the Start Calculation row. Instructions remain visible. Back cancels.
The test duration, refresh counting, FPS calculation, and machine-specific
cycle calculation are unchanged.

After a valid result, select **Save Timing To Config**. A custom Config saves
only its timing metadata and restarts. A factory Config instead offers a name
for a new custom Config, using the existing New Config/save-current-settings
flow. Back, Cancel, or an empty name makes no changes. Protected custom Configs
reject saving; factory Configs are never written.

Custom `config.txt` stores independent `timing_ntsc` and `timing_pal` values.
Only the measured standard's field is updated, through existing Config
transactional storage. The other field survives saves, renames, machine
changes, and restarts. Saving requires an HDMI result matching the running
standard, FPS within the existing 49–51 or 59–61 ranges, and a cycle rate
within 500000–2500000, covering the supported machines. Malformed stored
rates are ignored.

Config selection occurs after the emulator cores have captured boot timing.
To keep that architecture, startup checks the selected Config's matching
saved value before launching the emulator. If necessary it updates only the
timing command-line options and restarts once. No HDMI mode definition is
changed by this timing update. Temporary `e64_timing_base` and
`e64_cycles_base` command-line fields retain the original timing. Config
switches and return from Start Once restore it when appropriate, preventing
calibration from leaking into an uncalibrated Config. Networking, HDMI audio,
and other command-line arguments are retained. Failed updates are reported
through the existing Config boot message.

Pi 3B+ hardware results supplied by the user are regression inputs, not
changes to firmware factory defaults:

| Standard | Actual FPS | Calculated cycles per second |
| --- | --- | --- |
| NTSC | 59.826667 | 1022736 |
| PAL | 50.000000 | 982800 |

Run `bash tools/configs_test/run_tests.sh`. It includes the production timing
UI callbacks, cancellation and factory creation, both hardware inputs,
validation, independent persistence, Config switching, Start Once return,
factory protection, and NTSC/PAL HDMI mode preservation.
