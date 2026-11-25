========================================================================
 E64 - Enhanced 64
 WI-FI DEVICE FIRMWARE
========================================================================

FILES - /firmware
------------------------------------------------------------------------
Keep Wi-Fi device firmware here, preserving vendor capitalization and
extensions. The Pi 3B+ staged set is:

  brcmfmac43455-sdio.bin        Device firmware
  brcmfmac43455-sdio.txt        Board/device parameters
  brcmfmac43455-sdio.clm_blob   Regulatory data

All three are required as a complete set for this device. Other Pi models
may need different vendor files; do not rename files to imitate a set.
The existing driver selects the appropriate firmware for the hardware.
Ethernet does not require Wi-Fi device firmware.

SETTINGS AND BOOT FIRMWARE
------------------------------------------------------------------------
Credentials belong in /system/wifi-settings.conf, with
/system/wpa_supplicant.conf as fallback when the first file is absent.
See /system/README-system.txt and network-readme.txt for setup details.
Raspberry Pi boot firmware (bootcode.bin, start.elf and fixup.dat) must
remain at root; it is distinct from the Wi-Fi firmware in this directory.
Preserve all third-party firmware licenses and notices supplied with it.
