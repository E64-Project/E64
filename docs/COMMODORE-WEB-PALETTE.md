# E64 Web UI: Commodore palette and file icons

This Web UI uses the same Godot C64 palette already selected by the firmware:
`third_party/vice-3.3/data/C64/godot.vpl`. The native menu and emulation palettes
are unchanged. CSS tokens live in `src/webui/assets/style.css`.

| C64 color | RGB |
|---|---|
| Black | #000000 |
| White | #FFFFFF |
| Red | #880000 |
| Cyan | #AAFFEE |
| Purple | #CC44CC |
| Green | #00CC55 |
| Blue | #0000AA |
| Yellow | #EEEE77 |
| Orange | #DD8855 |
| Brown | #664400 |
| Light Red | #FE7777 |
| Dark Gray | #333333 |
| Medium Gray | #777777 |
| Light Green | #AAFF66 |
| Light Blue | #0088FF |
| Light Gray | #BBBBBB |

The main background is a darker neutral gray (#141414); panels, sidebar,
page headers, File Manager, and popups are black. Inputs use #1F1F1F,
hover surfaces #1C1C1C, decorative borders #444444, primary text #EEEEEE,
and dim text #999999. Controls have Medium Gray borders. Page titles are
Green, primary buttons Orange with black text, selected navigation Brown
with white text, links Light Blue, and keyboard focus Cyan. Help headings
and section rules use Orange. Status colors retain their meanings. Existing
logo/rainbow artwork remains unchanged; action buttons use flat colors.

The original nine 16×16 SVG assets use integer pixel rectangles and these
C64 colors. Their distinct outlines, cutouts, and details identify the types
without relying on color. Brown cassette reels and outline use Light Gray
for contrast. Each icon has an accessible type label; filenames remain text.

| Category | Extensions / rule | Shape / color |
|---|---|---|
| Directory | Actual directory metadata, always first | Tabbed folder / Yellow |
| Floppy image | d64, d71, d81, g64, d67, d80, d82, d1m, d2m, d4m | 5.25-inch floppy with hub and slot / Light Blue |
| Hard disk image | dhd | Platter, actuator and connectors / Light Gray |
| Cartridge image | crt | Cartridge case and contact fingers / Orange |
| Tape image | tap, t64 | Cassette with two reels / Brown, Light Gray outline |
| Program | prg, p00 | Folded document and code marks / Light Green |
| Snapshot | vsf | Camera and lens / Purple |
| ROM | rom | Chip with pins and notch / Cyan |
| Unknown | Everything else | Folded file / Medium Gray |

Extensions are case-insensitive and use only the final filename suffix.
The existing supported d1m/d2m/d4m images retain floppy recognition.
Ambiguous bin/img, extensionless files, and dotfiles remain generic; no ROM
assumption is made. A directory named `games.d64` always uses the folder.
Icons never change file capabilities, sorting, paths, or action handlers.

Verification:

```sh
node tools/webui_test/run_tests.mjs
python3 tools/webui_test/commodore_icons_test.py --sheet build/commodore-web-icons
python3 tools/webui_test/unified_ui_browser_check.py --desktop-only
```

The Python test checks exact palette values, >=4.5:1 selected text contrast
pairs, pixel dimensions/coordinates, high-contrast shape coverage, and
pairwise grayscale shape differences. The optional Pillow contact sheet is
a diagnostic, not a browser screenshot. The real Firefox harness checks
both desktop viewports, icon geometry/loading, all four page surfaces and
existing popup/File Manager operations; it reports blocked startup honestly.
