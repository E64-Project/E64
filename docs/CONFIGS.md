# E64 V1 Configs — Stage 2

The Config list exposes one immutable factory Config, `Default` (NTSC).
The `*` marks the running Config independently of the cursor. The active
heading shows its name. PAL emulation and custom PAL Configs remain available.
The protected `_factory-pal` identity remains readable for saved selections
and explicit PAL video changes, but has no separate card or list entry.
Creating a custom Config captures the actual running PAL/NTSC machine.

Fresh startup, a missing selection, a corrupt selection, an unreadable user
Config, or an incompatible user machine selects Default NTSC. Startup does
not rewrite corrupt selection data automatically. A failed PAL machine lookup selects NTSC and
tries its machine entry. If neither timing can be applied, firmware defaults
run on the video mode that already booted; this is reported in the menu.
A failed selection write does not prevent this boot from continuing.

Hold C= at power-on for protected Default NTSC, including when held
continuously from power-on. Shift+C= has no special recovery function and
also selects NTSC because C= is held. Shift alone does not change selection.
To create a PAL Config, load Default, choose PAL in the existing video
settings, and save a custom Config. Normal boot loads the last selected
Config (subject to Start once). The
passive GPIO sampler requires a stable C= key and restores every row
within its bounded 50ms window. It runs only when GPIO recovery is enabled
and DPI/GPIO output use permits it. The former C=+F7 reset is removed from
boot and runtime. F7 is an ordinary key; adding it to C= does not invoke a
separate reset or extend the boot sampling window. Firmware or video failures
before the sampler runs still require external repair.

Factory Configs cannot be saved, renamed, deleted, unprotected, or overwritten
through native, filesystem, HTTP, editor, or upload interfaces. Common native
settings and VICE resources are defined in `src/configs/config_factory.c`.
Both use stock ROM names, Godot palette, keyboard mapping and automatic drive
selection. Factory audio is Auto, with the global saved audio preference in
`cmdline.txt` retained for user Configs. Factory edits are temporary; use
New Config From Current Settings to save a writable copy.

User Config names accept 32 UTF-8 bytes. Existing folders, IDs, custom palettes,
ROM and drive choices, legacy `settings.txt`, and `settings-<machine>.txt` remain
readable. Startup never converts or renames clean user files. Switch to changes
the persistent selection. Start once returns to the persistent Config on the
next power-on; an emulator-requested restart retains the one-time session.
Factory selections are always persistent.

Save Settings and New Config snapshots stage native and VICE files before
committing either. Metadata, browser edits and uploads use the same Stage 1
recoverable per-file transaction. `<file>.e64-new` is staging and
`<file>.e64-old` is rollback. Recovery restores OLD and never promotes abandoned
NEW; final readback and CRC verification precede retiring OLD. Browser editor
saves preserve `.bak`. A cut between native and VICE commits can leave complete
files from different save generations. Hardware power-cut qualification is
still required; host fault injection cannot qualify physical FAT-sector tears.

`/configs/active.txt` stores `config` and optional `once`, followed by
`selection_crc`. Verified `active.new` recovers the unlink/rename gap only
when the final is absent. Existing legacy selections without a CRC remain
readable. Default identity is `_factory-ntsc`; PAL is `_factory-pal`.
User identities contain lowercase letters, digits and hyphens.

Protection and legacy-deletion journals retain independent integrity checks
and fail closed. Native and Web deletion ask two cancel-first questions:
`Delete Config "NAME"?` then `Confirm permanent deletion of "NAME"?`.
Only the second Yes deletes. No, Back, Escape and Home cancel navigation.
Deletion refuses factory, protected, running, persistent Power-on and queued
Start Once Configs. It also refuses storage leases, attached assets and asset
references from other saved Configs. It never changes selection to permit deletion.

New deletions permanently remove the Config directory and its owned assets.
They create no recovery entry or countdown. Successful deletion releases the
ID immediately; ordinary name collision checks still protect existing folders.
Legacy deleted entries remain frozen across startup/reboot. The temporary
`Legacy Config Cleanup` control lists them for explicit permanent deletion with
the same two questions; it disappears after the last entry is cleared.
There is no normal Restore workflow. Existing legacy files are never silently purged.

Filesystem failures return an error. Partial child removal can be retried with
the metadata retained. A final directory-removal failure can leave an orphan
folder that continues to reserve its ID; inspect it before manual recovery.
A failed legacy-journal commit after file removal is reported as incomplete
cleanup and retains the reservation. Deletion is not a power-fail-atomic FAT
transaction. Host tests cannot qualify physical SD failures.

The retired Main architecture has no runtime Config, root settings loader,
startup actions, special save allowance or remembered machine. No Previous
Settings Config is created and no old settings are migrated. Existing root
`settings.txt`, `vice.ini`, `E64SET.NEW`, `E64SET.OLD` and `/configs/main` files
are left untouched and externally protected. The `main` directory name remains
reserved solely to avoid reusing preserved files. Historical November 7
checkpoints preserve the previous system. Installer cleanup is a separate,
after-hardware-validation task.

## Native navigation

Home while the native menu is open cancels popup navigation and key capture,
collapses inline folders, returns to the first selectable root entry and keeps
the root open. It never dispatches a selection or text submission. Closed-menu
Home continues through the ordinary C64 keyboard path. Back and Escape retain
their existing behavior.

The root header retains its frame dimensions and centered title. NTSC/PAL and
network indicators each have a six-cell content section with original CHARGEN
T-junction dividers. Footer navigation is inset four pixels symmetrically.
Root menu content starts four pixels higher; the viewport extends sixteen
pixels farther down. At the standard 200px menu height, twenty ordinary rows
fit instead of eighteen, with four pixels before the footer-divider cell.
Expanded-folder separators consume their normal eight pixels. Popup and file
browser row geometry is unchanged.

## Native Rename Config list

`configs_list_open()` returns a positive Config count, not CONFIGS_OK (zero).
Rename opens this snapshot, excludes immutable factory identities, and releases
it through the normal list-popup callback on Back, Escape, Home or selection.
A missing /configs directory is a valid factory-only list; an allocation or
filesystem failure is reported separately and clears the snapshot. The empty
list displays "No custom Configs to rename" with a Back action.

Existing custom protection guards deletion, not display-name edits. Running,
persistent Power-on and Start Once Configs can still be renamed because their
IDs do not change. Choosing Rename re-reads current metadata before closing
the list. Submission changes only the display name; cancellation writes
nothing. Factory/invalid/inactive IDs remain forbidden. A name already used by
another live Config (ASCII case-insensitive, after normal trimming) or the
factory Default is rejected. The collision check owns a separate directory
iteration and never opens/closes the native Config snapshot. It fails safely
if another existing Config's metadata cannot be checked.
