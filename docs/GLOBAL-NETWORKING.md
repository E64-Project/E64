# Global networking

Network device selection, Web UI enablement/PIN, modem address, and modem baud
are global preferences in `/system/network-prefs.txt`. They are loaded for
Default NTSC, Default PAL, custom Configs, and C= factory recovery alike.
The Network/Web UI save-and-reboot actions save this global file, including
while a protected factory Config is running. They do not save Config payloads.

IP addressing, DNS, NTP, timezone, and DST keep their existing global
`/system/network.cfg` storage. Wi-Fi country, SSID, and credentials keep their
existing global Wi-Fi configuration file. Switching Configs does not rewrite
these files. Native Config settings no longer save or apply network preference
fields.

The previous startup loader read network device and Web UI settings from the
running Config and returned immediately for factory Configs. This caused
networking to revert to Off when switching to a factory Config. The global
loader replaces that behavior.

If global preferences are absent, startup reads the current custom Config's
legacy native settings, or preserved root `/settings.txt` when no custom
settings are available, and migrates recognized preferences once. Legacy files
are read only. Once the global file exists, older Config-specific network
values are ignored. No Config directories are searched to guess a preference.
If neither legacy source exists, the existing Off defaults remain until the
user saves a network selection.

The global writer checks file operations, stages a replacement, and retains
an `.old` file for recovery if interrupted between renames. Invalid global
preferences report a load error rather than importing another Config's values.
Credentials are never copied into Configs or command-line arguments.

Machine switching also preserves network/service command-line options against
machine-definition overrides, bare options, values containing `=`, long values,
tabs/repeated spaces, and a final line without a newline. Oversized rewritten
command lines are rejected before replacement.

Run `python3 tools/network_test/run_tests.py`. This separate regression suite
executes the production startup loader, preference storage, native menu
load/save helpers, machine switching, and Config lifecycle using temporary
storage. It covers Ethernet and Wi-Fi across factory/custom NTSC/PAL, Start
Once, C= recovery, legacy migration, preference recovery, credential/service
file preservation, and command-line preservation.
