import { showHelp } from "./help_dialog.js";
import { openJiffyCommands, closeJiffyCommands } from "./jiffydos_commands.js";

// References: project drive ROM documentation and the current native menus.
// JiffyDOS descriptions and five-column layout are the user's approved design.
// E64 actions always arrive live from the running Config via /api/status.
const standardDrives = [
  ["1541", ".d64", "170 KB", "Single"],
  ["1541-II", ".d64", "170 KB", "Single"],
  ["1571", ".d71", "340 KB", "Single"],
  ["1581", ".d81", "800 KB", "Single"],
  ["FD-2000", ".d1m", "1.6 MB", "Single"],
  ["FD-4000", ".d2m", "3.2 MB", "Single"],
  ["CMD HD", ".dhd", "Variable", "Single"],
];
const ieeeDrives = [
  ["2031", ".d64", "170 KB", "Single"],
  ["2040", ".d67", "170 KB", "Dual"],
  ["3040", ".d64", "170 KB", "Dual"],
  ["4040", ".d64", "170 KB", "Dual"],
  ["8050", ".d80", "500 KB", "Dual"],
  ["8250", ".d82", "1.0 MB", "Dual"],
  ["SFD-1001", ".d82", "1.0 MB", "Single"],
];
const standardRoms = [
  ["1541", "dos1541", ""], ["1541-II", "d1541II", "JD-d1541II"],
  ["1570", "dos1570", ""], ["1571", "dos1571", "JD-dos1571"],
  ["1581", "dos1581", "JD-dos1581"], ["FD-2000", "dos2000", ""],
  ["FD-4000", "dos4000", ""], ["CMD HD", "dosCMDHD", ""],
];
const ieeeRoms = [
  ["2031", "dos2031"], ["2040", "dos2040"],
  ["3040", "dos3040"], ["4040", "dos4040"],
  ["8050", "dos1001"], ["8250", "dos1001"],
  ["SFD-1001", "dos1001"],
];
// Static project-controlled reference data only. Live action values use textContent.
function table(headers, rows, className) {
  return `<div class="help-table-scroll"><table class="${className}"><thead><tr>${headers.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
const driveNumbers = `<section class="drive-number-group"><h4>Single Mechanism</h4><p>2031 and SFD-1001 can use Drive 8, 9, 10, or 11.</p><hr><h4>Dual Mechanism</h4><p>2040, 3040, 4040, 8050, and 8250 use paired drives: 8/9 or 10/11.</p><p>First mechanism: Drive 8 or 10. Second mechanism: Drive 9 or 11.</p></section>`;
const commodore = `<span class="modifier-keycap commodore-keycap"><img class="commodore-symbol" src="/commodore-c-logo.svg" width="24" height="23" alt="Commodore"></span>`;
const jiffyActions = ["Directory", "DList", "Load", "TList", "Load/Run", "Save", "Load ML", "Scratch"];
function hotkeysHelp() {
  return `<div class="hotkeys-scroll" tabindex="0" role="region" aria-label="Scrollable E64 and JiffyDOS function key reference"><table id="live-hotkeys" class="hotkeys-table" aria-label="E64 and JiffyDOS hotkeys">
    <colgroup><col class="modifier-col"><col class="action-col"><col class="physical-key-col"><col class="action-col"><col class="jiffy-key-col"></colgroup>
    <thead><tr><th aria-hidden="true"></th><th scope="col" class="e64-heading"><span class="hotkeys-e64-wordmark"><img class="hotkeys-e64-logo" src="/e64-long.png" alt="E64" width="1615" height="974"></span></th><th scope="col"><span class="c64-key-heading">C64 KEY</span></th><th scope="col" class="jiffy-heading"><img class="jiffydos-logo" src="/jiffydos.png" alt="JiffyDOS" width="243" height="67"></th><th aria-hidden="true"></th></tr></thead>
    <tbody>${[0, 1, 2, 3].map(pair => {
      const odd = pair * 2 + 1, even = odd + 1;
      return `<tr class="hotkey-pair">
        <td class="e64-side"><div class="hotkey-halves"><div class="hotkey-cell modifier-symbol">${commodore}</div><div class="hotkey-cell"><span class="modifier-keycap">CTRL</span></div></div></td>
        <td class="e64-side"><div class="hotkey-halves"><div class="hotkey-cell" id="e64-action-${pair}" aria-label="Commodore plus F${odd}">Unavailable</div><div class="hotkey-cell" id="e64-action-${pair + 4}" aria-label="CTRL plus F${odd}">Unavailable</div></div></td>
        <td class="physical-key"><span class="hotkey-divider hotkey-divider-left" aria-hidden="true"></span><span class="hotkey-divider hotkey-divider-right" aria-hidden="true"></span><div class="c64-keycap" aria-label="F${odd} / F${even}"><span class="key-upper">F${odd}</span><span class="key-lower">F${even}</span></div></td>
        <td class="jiffy-side"><div class="hotkey-halves"><div class="hotkey-cell">${jiffyActions[odd - 1]}</div><div class="hotkey-cell">${jiffyActions[even - 1]}</div></div></td>
        <td class="jiffy-side"><div class="hotkey-halves"><div class="hotkey-cell" aria-label="Unshifted"></div><div class="hotkey-cell" aria-label="Shift plus F${odd} gives F${even}"><span class="modifier-keycap">SHIFT</span></div></div></td>
      </tr>`;
    }).join("")}</tbody></table></div>`;
}
// dos1570 is a VICE resource, but E64 does not expose a 1570 model.
// Retain ROM resources without advertising an unsupported model.
const standardReference = standardDrives.map(row => [...row, ...standardRoms.find(rom => rom[0] === row[0]).slice(1)]);
const ieeeReference = ieeeDrives.map(row => [...row, ieeeRoms.find(rom => rom[0] === row[0])[1], ""]);
const referenceHeaders = ["Model", "Image", "Capacity", "Type", "ROM", "JiffyDOS ROM"];
const pages = {
  drives: ["Drive Reference", `<h4 class="drive-section-heading"><span>Standard Drives</span><span class="drive-section-description">JiffyDOS requires both its C64 KERNAL and a matching Drive ROM</span></h4>${table(referenceHeaders, standardReference, "drive-reference combined-drive-reference")}<div class="ieee-reference-heading"><button type="button" class="ieee-reference-toggle" aria-expanded="false" aria-controls="ieee-reference"><strong>IEEE-488 Drives</strong></button><span class="drive-section-description">Requires the IEEE-488 interface to be enabled</span><a class="btn ieee-setup" href="#/instructions/ieee488">IEEE-488 Setup</a></div><section id="ieee-reference" hidden>${table([...referenceHeaders.slice(0, 5), ""], ieeeReference, "drive-reference combined-drive-reference ieee-rom-reference")}<hr>${driveNumbers}</section>`],
  ieee488: ["IEEE-488 Setup", `<ol><li>Place the IEEE-488 interface ROM at <code>SD /carts/eprom.bin</code>.<br>Place the matching drive ROM in <code>SD /drives</code>.</li><li>Open Drives and enable IEEE-488 Interface.<br>Exit the menu to restart the C64.</li><li>Open Drives and select the drive number.<br>Choose Change Drive Model, then the IEEE-488 model.</li><li>Use Attach Disk Image to attach a matching disk image.</li></ol>`],
  sid: ["Dual SID Setup", `<ol><li>Open Sound and enable Dual SID.</li><li>Set the SID2 address (ie: 0xD420).</li><li>Choose SID2 Model: 6581 or 8580.</li><li>Reset the C64 after changing the address.</li><li>Save the settings to your custom Config.</li></ol><hr><h4>Pseudo Stereo</h4><ol><li>Enable Dual SID.</li><li>Set SID2 Address to the same as SID1.</li></ol><p class="deliberate-lines">Choose different chip models, such as<br>a 6581 for SID1 and an 8580 for SID2.</p><hr><p class="deliberate-lines">Both SIDs receive the same register writes.</p><p class="deliberate-lines">It's the differences in their characteristics<br>that produce the pseudo-stereo effect.</p>`],
  mouse: ["GEOS Mouse Setup", `<ol><li>Connect a USB mouse.</li><li>Open Joyports and set Port 1 to USB Mouse (1351).</li><li>Save your custom Config.</li><li>Start GEOS and select the 1351 Mouse driver.</li></ol><hr><h4>Mouse Compatibility</h4><p class="mouse-compatibility-note"><span>Note: </span><span>The 1351 protocol does not expose<br>the scroll wheel or middle button.</span></p>`],
  hotkeys: ["Hotkeys", hotkeysHelp()],
  commands: ["JiffyDOS Commands", ""],
  navigation: ["Menu Navigation Keys", `<div class="navigation-keys"><strong>CRSR Keys</strong><span>:</span><span>Move Up and Down through menu items.</span><strong>RETURN</strong><span>:</span><span>Selects an item or opens a menu.</span><strong>← Key</strong><span>:</span><span>Exits the menu.</span></div><hr><h4>Extended Menu Navigation</h4><div class="navigation-keys"><strong>HOME</strong><span>:</span><span>Closes all expanded menus and returns to the Main Menu.</span><strong>↑ Key</strong><span>:</span><span>Closes only the current submenu section.<br>Other menu sections will stay as they are.</span></div><p>Note: This is the up-arrow character key, not the cursor-up key.</p><hr class="navigation-lower-divider"><div class="safe-start"><h4>Safe Start</h4><p><span>Hold down the</span> ${commodore} <span>key during boot to load the Default Profile</span></p></div><hr class="navigation-footer-divider"><div id="navigation-note-slot"></div>`],
  hardware: ["Hardware", `<section><h4>Power Supply and Wiring</h4>
<p>For the Raspberry Pi 3B+, a well-regulated 5.1V, 3A supply is recommended.</p>
<p><strong>The entire power path matters.</strong> A good power supply needs low-resistance cables and firm, reliable connectors. Resistance wastes some of the voltage before it reaches the Pi. Even short jumper wires can cause problems, and poor connectors can introduce voltage drop. A good supply cannot compensate for poor connections between it and the Pi.</p>
<p>USB peripherals and the fan increase power demand. Choose suitable wire and connectors throughout the power path, and include these extra loads when selecting a supply.</p></section><hr>
<section><h4>Cooling Fan</h4>
<p>E64 switches an external 5V DC fan through an NPN transistor. BCM GPIO11 (physical header pin 23) is the control signal: active HIGH (3.3V logic) means fan ON; active LOW means fan OFF. The fan takes power from the incoming regulated 5V power line before it branches to the Raspberry Pi.</p>
<p>In Auto mode, E64 checks the processor temperature about once per second. The fan turns ON at or above Fan On Temp and OFF at or below Fan Off Temp. Between these thresholds it keeps its previous state. The OFF threshold must be lower so that small temperature changes do not repeatedly switch the fan on and off.</p>
<p>The default mode is Off, with thresholds of 55 °C and 50 °C. Temperatures must be within 30–80 °C, with the off threshold strictly below the on threshold. Off keeps the fan stopped. On runs it continuously. Auto runs the fan if the temperature is unavailable. During shutdown E64 requests ON in On and Auto modes. Reset or loss of power can subsequently stop the fan.</p>
<p>In the native System menu, open Cooling Fan, choose Off, On, or Auto with Left and Right, and set both temperatures, then select <strong>Save Fan Settings</strong>. Edits alone do not apply or persist. A successful save applies all three settings together and stores them in global preferences at <code>/system/fan-prefs.txt</code>, shared across Configs and loaded at startup. Check the save result; a failed save keeps the previously applied settings. Automatic control is available on supported E64 Pi GPIO hardware with DPI disabled.</p>
<h4 class="fan-circuit-heading">Fan Control Circuit</h4>
<figure class="hardware-schematic"><img src="/fan-switch.svg" width="820" height="470" alt="Fan Control Circuit: +5 VDC to fan positive and D1 cathode; GPIO11 physical pin 23 through R1 to Q1 base B; R2 from base to common ground; collector C to fan negative and D1 anode; emitter E to common ground."></figure>
<div class="fan-specifications"><dl class="fan-parts"><dt>R1:</dt><dd>470 Ω</dd><dt>R2:</dt><dd>10 kΩ</dd><dt>Q1:</dt><dd>PN2222A / 2N2222A</dd><dt>D1:</dt><dd>1N4001</dd><dt>FAN:</dt><dd>5V DC (150mA Max)</dd></dl><dl class="fan-logic"><dt>GPIO11 HIGH</dt><dd>= Fan ON</dd><dt>GPIO11 LOW</dt><dd>= Fan OFF</dd></dl></div>
<p>These ordinary parts are commonly available from Amazon or electronics suppliers. A suitable replacement NPN switching transistor may be used if its current rating, base-drive requirements, and pinout are appropriate.</p>
<p><strong>2N2222A and PN2222A pinouts can differ by package and manufacturer.</strong> Consult the datasheet for the exact part. Connect Collector (C), Base (B) and Emitter (E) as shown; do not assume a universal physical lead order.</p>
<p>D1 goes across the fan: its cathode (banded end) connects to the incoming +5V fan power branch and its anode connects to fan negative / Q1 collector. Reversing it can short the supply when Q1 turns on.</p>
<p>Electrical references: <a href="https://www.raspberrypi.com/documentation/computers/raspberry-pi.html">Raspberry Pi power, header and GPIO specifications</a>; <a href="https://www.onsemi.com/pdf/datasheet/pn2222a-d.pdf">onsemi PN2222A datasheet</a>; <a href="https://www.vishay.com/docs/88503/1n4001.pdf">Vishay 1N4001 datasheet</a>. Device current and thermal limits must be checked for the selected manufacturer and package; an absolute maximum is not a circuit load rating.</p></section>
<p class="help-annotation">Future hardware topics will include USB-to-RS-232.</p>`],
  storage: ["Storage", `<p class="storage-boot-warning"><strong>Do not connect external USB storage <br>until E64 has finished booting.</strong></p><ol><li>Disconnect external USB flash drives and external USB hard drives before starting or restarting E64.</li><li>Leave the boot SD card installed.</li><li>A permanently installed internal USB drive may remain connected.</li><li>Boot E64 and allow it to finish starting.</li><li>Connect external USB storage only after E64 is ready.</li><li>Wait for the newly connected drive to appear before using it in the File Manager.</li></ol><h4>Storage and drive names</h4>
<p>The SD card normally holds the boot and system files for E64.</p>
<p>The USB volumes hold user files, games, and disk images.</p>
<p>Connected USB volumes will appear as USB1, USB2, and USB3.</p>
<p>If available, volume labels are displayed (i.e., USB1: VOLUME1).</p>
<h4>File Manager</h4>
<p>Select a drive and open a folder.</p>
<p>Use Copy to create a copy of the file or folder, or Move to relocate the file or folder.</p>
<p>Upload sends files from your computer into the current folder on E64.</p>
<p>(You can also drag files into the currently open folder in File Manager.)</p>
<p>Download saves files from E64 to your computer.</p>
<p>Note: Folder downloads will be ZIP archives.</p>
<hr><h4>How Much Storage Do You Really Need?</h4>
<p>Commodore 64 programs tend to be extremely small.</p>
<p class="deliberate-lines">A standard D64 image is 175 KB (171 KiB). In theory, a typical<br>16 GB USB stick can hold close to 90,000 standard D64 images.</p>
<p>A reliable USB flash drive is more desirable than excessive capacity.</p>
<p class="deliberate-lines">It is best to organize your files into directories, such as Games,<br>Demos, and Utilities, to make large collections easier to navigate.</p>`],
  memory: ["Memory Expansion", `<h4>C64 memory and the REU</h4>
<p>The original C64 has 64 KB of RAM. A RAM Expansion Unit (REU) adds separate memory that compatible software transfers to and from C64 memory. It does not enlarge ordinary BASIC memory or make every C64 program use extra RAM automatically.</p>
<p>E64's native C64 memory expansion controls expose the REU. GeoRAM and other expansion devices are not offered in this menu. REU-aware software, such as GEOS with an appropriate REU driver, can use it for a RAM disk or workspace; REU-specific demos and utilities may require a particular size.</p>
<h4>Enable and configure</h4><ol><li>Open Cartridge → RAM Expansion.</li><li>Set Memory Size to 128k, 256k, 512k, 1024k, 2048k, 4096k, 8192k, or 16384k (128 KB through 16 MB).</li><li>Turn Enabled on before starting compatible software. Turn it off to disable the REU.</li><li>Save the settings to your custom Config to retain the configuration across restarts.</li></ol>
<p>The resource defaults are disabled and 512k. Choose the size requested by the software; more is not always more compatible. Enable and size changes apply immediately without a forced C64 reset. Restart the program or reset the C64 if it detects expansion memory only at startup. Changing size or disabling the REU can discard working contents; save them first.</p>
<h4>REU File</h4><p>With the REU enabled, Load File > loads a raw REU memory image and selects its supported size from the file length. Save As > writes an image to a chosen file; Save Now writes to the associated image. Clear Image removes the file association; it does not disable the REU or promise to erase its RAM. Save Now and Clear Image require an associated file.</p>
<p>Saving a Config preserves settings, not a snapshot of RAM contents. Use the REU File save actions to preserve memory data. Keep the image file available when reusing its configuration.</p>`],
  advanced: ["Advanced Drive Settings", `<p>Open Drives → Advanced Drive Settings. Each Drive 8–11 folder has its own settings; Virtual Devices is shared. These are compatibility tools: retain your working Config's defaults unless software requires a change.</p>
<h4>Drive model and filesystem</h4>
${table(["Setting", "Purpose and when to change it", "Defaults and compatibility"], [
["Change Model >", "Selects the emulated drive hardware. Match the software and disk image, for example 1541 with D64 or 1581 with D81.", "Keep the working model for ordinary use. Explicit model selection leaves automatic model selection. IEEE-488 models require the interface ROM and interface enabled; see Drive Reference."],
["IEC FileSystem", "Enables the emulated IEC filesystem device for the unit; use it to access host files without a full emulated disk mechanism.", "Normally off. For directory access, disable True Drive Emulation for that unit and select an IEC directory. This is not a replacement for drive CPU emulation: custom fast loaders and disk protection may fail."],
["Select IEC Dir >", "Chooses the host directory used for filesystem access; useful for loose program files.", "Keep the existing directory unless changing the collection exposed to the C64. It does not attach a disk image; filesystem access does not reproduce disk tracks or drive code."],
["True Drive Emulation", "Emulates the drive CPU and hardware for drive code, timing, and many fast loaders.", "Keep enabled for disk software needing accurate drive behavior. Disabling can reduce emulation work but breaks software that runs code in the drive. A matching model and ROM still matter."],
["Virtual Devices", "Enables KERNAL serial traps for faster high-level device access; applies globally, not just to the selected drive.", "Keep your Config's value unless diagnosing loading or using filesystem access. Traps do not emulate custom drive code; use True Drive Emulation for such software. Nonstandard KERNALs can affect trap compatibility."],
], "drive-reference")}
<h4>CMDHD Mode</h4><p>This menu spelling refers to the CMD HD model. Selecting a mode resets the selected drive with simulated front-panel buttons. It is an operation, not a permanent Config preference.</p>
${table(["Value", "Use", "Default / compatibility"], [
["Normal", "Resets the drive for ordinary disk access.", "Normal operating choice; return here after maintenance."],
["Initialization", "Resets with the SWAP 8 and SWAP 9 buttons held for CMD HD installation / initialization tools.", "Use only with the appropriate tools and image. Initialization utilities can change disk contents; leave Normal for ordinary loading."],
["Configuration", "Resets with the write-protect button held for CMD HD configuration tools.", "Use only when configuring a CMD HD; leave Normal for games. These button modes do not provide equivalent features on other drive models."],
], "drive-reference")}
<h4>Parallel Cable</h4><p>Choices are None, Standard, Dolphin DOS, and Formel 64. They emulate different parallel connections between the C64 and a compatible drive for matching fast-loader systems. Leave None unless the software and drive ROM require that cable. The supported parallel drive families are 1541 and 1571. Selecting a cable alone does not install a fast DOS; the wrong cable, ROM, or drive model can prevent communication. These choices do not add physical USB or GPIO cables.</p>
<h4>Drive RAM expansion</h4><p>Each toggle adds an 8 KB RAM window in the emulated drive's address space where the drive model implements it. This is drive memory, not C64 memory or an REU. Use only for drive software or a replacement drive DOS that explicitly requires it. All five default to off; extra RAM can replace expected memory mappings and break compatibility.</p>
${table(["Setting", "Drive address window", "When to use / default"], [
["RAM 2000", "$2000–$3FFF", "Only when drive software requests this window; otherwise off."],
["RAM 4000", "$4000–$5FFF", "Only when drive software requests this window; otherwise off."],
["RAM 6000", "$6000–$7FFF", "Only when drive software requests this window; otherwise off."],
["RAM 8000", "$8000–$9FFF", "Only when drive software requests this window; otherwise off."],
["RAM A000", "$A000–$BFFF", "Only when drive software requests this window; otherwise off."],
], "drive-reference")}
<p>The 1541 family implements all five windows; the 1570/1571 mapping uses RAM 4000 and RAM 6000 (with hardware I/O taking part of the 4000 window). Other models have their own mappings; a visible toggle does not mean that every model uses that window. Drive RAM and parallel loaders need the emulated drive hardware, not just filesystem access.</p>
<p>Save resource settings to your custom Config to retain them. CMDHD Mode instead triggers a drive reset immediately. Configure devices before starting software; restart the program if it detected the old drive setup.</p><p><a href="#/instructions/drives">Drive Reference</a> · <a href="#/instructions/storage">Storage</a> · <a href="#/instructions/memory">Memory Expansion</a></p>`],
};
let currentTopic = "";
let setupOrigin = null;
let currentHotkeys = [];
let currentConfigId = "";
export function updateHotkeys(values, configId = "") {
  currentHotkeys = Array.isArray(values) ? values.slice(0, 8) : [];
  currentConfigId = typeof configId === "string" ? configId : "";
  const list = document.getElementById("live-hotkeys");
  if (!list) return;
  list.dataset.configId = currentConfigId;
  for (let slot = 0; slot < 8; slot++) {
    const action = document.getElementById("e64-action-" + slot);
    if (action) action.textContent = currentHotkeys[slot] || "Unavailable";
  }
}
export function showInstructions(id) {
  if (id === "roms") id = "drives"; // Preserve existing reference bookmarks.
  if (id === "jiffy") id = "hotkeys"; // Preserve existing bookmarked links.
  const popupBefore = document.getElementById("instructions-popup");
  popupBefore.append(document.getElementById("navigation-help-note"));
  const contentBefore = document.getElementById("instructions-content");
  if (id === "ieee488" && currentTopic === "drives") {
    setupOrigin = { nodes: Array.from(contentBefore.childNodes), scroll: popupBefore.scrollTop };
  } else if (id !== "ieee488" && id !== "drives") setupOrigin = null;
  const returning = id === "drives" && currentTopic === "ieee488" && setupOrigin;
  currentTopic = id || "";
  const referencePopup = document.getElementById("jiffydos-commands-popup");
  referencePopup.onclose = null;
  closeJiffyCommands();
  popupBefore.hidden = false;
  popupBefore.inert = false;
  const nav = document.getElementById("instructions-index");
  nav.replaceChildren();
  for (const [key, [title]] of Object.entries(pages)) {
    if (key === "ieee488") continue; // Setup is available beside the expandable drive reference.
    const link = document.createElement("a");
    link.href = "#/instructions/" + key;
    link.textContent = title;
    nav.append(link);
  }
  const page = pages[id];
  const content = document.getElementById("instructions-content");
  document.getElementById("instructions-title").textContent = page ? page[0] : "Instructions";
  if (returning) content.replaceChildren(...setupOrigin.nodes);
  else content.innerHTML = page ? page[1] : "<p>Select a topic above.</p>";
  if (id === "drives" && !returning) {
    const toggle = content.querySelector(".ieee-reference-toggle");
    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(expanded));
      document.getElementById("ieee-reference").hidden = !expanded;
    });
  }
  if (id === "commands") {
    const help = document.getElementById("instructions-popup");
    help.onclose = null;
    if (help.open) help.close();
    openJiffyCommands();
    const commands = document.getElementById("jiffydos-commands-popup");
    commands.onclose = () => {
      if (location.hash === "#/instructions/commands") location.hash = "#/instructions";
    };
    return;
  }
  updateHotkeys(currentHotkeys, currentConfigId);
  const popup = document.getElementById("instructions-popup");
  popup.dataset.topic = id || "";
  const navigationNote = document.getElementById("navigation-help-note");
  navigationNote.hidden = id !== "navigation";
  // Move the existing annotation only after the new topic content is rendered.
  if (id === "navigation") document.getElementById("navigation-note-slot").append(navigationNote);
  else popup.append(navigationNote);
  const commandsButton = document.getElementById("hotkeys-commands");
  commandsButton.hidden = id !== "hotkeys";
  commandsButton.onclick = () => {
    popup.hidden = true;
    popup.inert = true;
    const reference = document.getElementById("jiffydos-commands-popup");
    reference.onclose = () => {
      if (location.hash === "#/instructions/hotkeys") {
        popup.hidden = false;
        popup.inert = false;
        commandsButton.focus();
      }
    };
    openJiffyCommands(commandsButton);
  };
  if (page && popup.show) {
    if (!popup.open) showHelp(popup);
    if (returning) {
      popup.scrollTop = setupOrigin.scroll;
      content.querySelector(".ieee-setup").focus({ preventScroll: true });
      setupOrigin = null;
    }
    popup.onclose = () => {
      closeJiffyCommands();
      if (location.hash.startsWith("#/instructions/"))
        location.hash = id === "ieee488" && setupOrigin ? "#/instructions/drives" : "#/instructions";
    };
  } else if (!page && popup.open) popup.close();
}

export function hideInstructions() {
  document.getElementById("jiffydos-commands-popup").onclose = null;
  closeJiffyCommands();
  const popup = document.getElementById("instructions-popup");
  if (popup.open) popup.close();
}
