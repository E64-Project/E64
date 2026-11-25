import { rememberVolumes, volumeLabel } from "./volumes.js";
import { chooseRawCartridge } from "./raw_cartridge.js";
import { createFileIcon } from "./file_icons.js";
import { confirmE64, promptE64, createPopupHeader } from "./dialog.js";
// Files view: browse the SD card and USB volumes, upload, download, rename, delete, create
// folders, autostart, and open the config-file and BASIC editors. Each row has one
// "Actions" button that opens a menu of what applies to that entry;
// clicking the name does the most common one (open a folder, run, edit).

import { $, fmtBytes, normPath, parentPath } from "./util.js";
import * as api from "./api.js";
import { openEditor, openBasicEditor } from "./editor.js";
import { LOAD_ADDRESS, parsePrg } from "./basic.js";
import { toggleMenu } from "./menu.js";
import { canRun, hasBasicEditor, machineName } from "./machine.js";

// This session exists only when LOAD opens Files from the Datasette.
let tapeSelection = null;
export function beginTapeSelection() {
  tapeSelection = {};
  $("fb-tape-cancel").hidden = false;
}
export function endTapeSelection() {
  tapeSelection = null;
  $("fb-tape-cancel").hidden = true;
}
export function cancelTapeSelection() {
  if (!tapeSelection) return;
  endTapeSelection();
  location.hash = "#/datasette";
}

// current location (set by loadDir)
let fbVol = localStorage.getItem("bmc64-files-volume") || "USB";
let fbPath = "/";
let fbNames = new Set(); // file names in the current folder (for overwrite checks)
let availableVolumes = [];
let filesRequest = 0;
let volumesRequest = 0;
let lastListingRequest = 0;
let lastListingVolume = "";
const STORAGE_VOLUMES = ["SD", "USB", "USB2", "USB3"];

// Open a folder from another page without changing the saved Files preference.
export function selectFilesVolume(vol) {
  if (STORAGE_VOLUMES.includes(vol) && vol !== fbVol) {
    ++filesRequest; // invalidate a listing for a previously selected volume
    fbVol = vol;
  }
}

function renderVolumeButtons() {
  for (const vol of STORAGE_VOLUMES) {
    const button = $("fb-vol-" + vol);
    button.hidden = vol !== "SD" && !availableVolumes.includes(vol);
    button.textContent = volumeLabel(vol);
    button.classList.toggle("btn-primary", vol === fbVol);
    button.setAttribute("aria-pressed", vol === fbVol ? "true" : "false");
  }

}

const extOf = (name) => (name.split(".").pop() || "").toLowerCase();

// Types this machine's Autostart accepts (the device says which).
function isRunnable(name) {
  return canRun(extOf(name));
}

// Disks, tapes and programs are autostarted, like the menu's Autostart item;
// a cartridge image is attached (which resets the machine).
const runVerb = (name) =>
  extOf(name) === "crt" ? "Attach cartridge" : "Load & Run";


export function filesHash(path) {
  path = normPath(path);
  if (path === "/") return "#/files";
  return "#/files" + path.split("/").map(encodeURIComponent).join("/");
}

export function pathFromHash() {
  const raw = (location.hash || "").slice("#/files".length);
  if (!raw) return "/";
  try {
    return normPath(raw.split("/").map(decodeURIComponent).join("/"));
  } catch (e) {
    return "/";
  }
}

function renderCrumbs(vol, path) {
  const box = $("fb-crumbs");
  box.textContent = "";
  const label = document.createElement("span");
  label.textContent = "Path: ";
  label.className = "fb-path-label";
  box.appendChild(label);
  const root = document.createElement("a");
  root.href = filesHash("/");
  root.textContent = vol === "USB" ? "USB1" : (vol || "SD");
  box.appendChild(root);

  const parts = normPath(path).split("/").filter(Boolean);
  let acc = "";
  parts.forEach((seg, i) => {
    acc += "/" + seg;
    const sep = document.createElement("span");
    sep.className = "sep";
    sep.textContent = "/";
    box.appendChild(sep);
    if (i === parts.length - 1) {
      const cur = document.createElement("span");
      cur.className = "cur";
      cur.textContent = seg;
      box.appendChild(cur);
    } else {
      const a = document.createElement("a");
      a.href = filesHash(acc);
      a.textContent = seg;
      box.appendChild(a);
    }
  });
}

// A file name that acts as a link running `action` when clicked.
function nameLink(name, title, action) {
  const a = document.createElement("a");
  a.href = "#";
  a.title = title;
  a.textContent = name;
  a.addEventListener("click", (ev) => {
    ev.preventDefault();
    action();
  });
  return a;
}

// The entries of a row's Actions menu; empty when nothing applies (the
// device marks its own config files and /firmware as protected).
function rowActions(e, path) {
  const items = [];
  if (tapeSelection && !e.dir && extOf(e.name) === "tap") {
    return [{ label: "Load Tape", run: () => loadTape(path, e.name) }];
  }
  if (!e.dir && extOf(e.name) === "rom" && machineName() === "C64") {
    items.push({ label: "Load ROM...", run: () => loadRawCartridge(path, e) });
  }
  if (!e.dir && isRunnable(e.name)) {
    items.push({ label: runVerb(e.name), run: () => runFile(path, e.name) });
  }
  if (!e.dir && extOf(e.name) === "tap") {
    items.push({ label: "Load Tape", run: () => loadTape(path, e.name) });
  }
  if (!e.dir && ["d64", "d71", "d81", "d82", "g64", "d1m", "d2m", "d4m", "dhd"].includes(extOf(e.name))) {
    for (const unit of [8, 9, 10, 11]) {
      const label = extOf(e.name) === "dhd"
        ? `Mount CMD HD (drive ${unit})` : `Mount Only (drive ${unit})`;
      items.push({ label, run: () => mountDisk(path, e.name, unit) });
    }
  }
  if (!e.dir && extOf(e.name) === "prg" && isRunnable(e.name)) {
    items.push({ label: "Load Only", run: () => loadPrg(path, e.name) });
  }
  if (!e.dir && extOf(e.name) === "txt") {
    items.push({ label: "View Text", run: () => openEditor({ vol: fbVol, path, name: e.name, readOnly: true }) });
    if (e.edit) items.push({ label: "Edit Text", run: () => editFile(path, e.name) });
  } else if (!e.dir && e.edit) {
    items.push({ label: "Edit…", run: () => editFile(path, e.name) });
  }
  // Whether a .prg is BASIC can only be told by reading it, which is left to
  // the click rather than done for every file in a folder listing.
  if (!e.dir && extOf(e.name) === "prg" && hasBasicEditor()) {
    items.push({ label: "Edit listing…", run: () => editListing(path, e) });
  }
  if (!e.dir) {
    items.push({ label: "Download", href: api.downloadUrl(fbVol, path) });
  } else if (!e.protected) {
    items.push({ label: "Download Folder", href: api.downloadFolderUrl(fbVol, path) });
  }
  if (!e.protected) {
    {
      items.push({ label: "Copy To >", run: () => transferEntry(path, e.name, false, e.dir) });
      items.push({ label: "Move To >", run: () => transferEntry(path, e.name, true, e.dir) });
    }
    items.push({ label: "Rename >", run: () => renameEntry(path, e.name) });
    items.push({ label: "Delete", danger: true,
                 run: () => deleteEntry(path, e.name, e.dir) });
  }
  return items;
}

function actionsButton(e, path) {
  const items = rowActions(e, path);
  if (!items.length) return null;
  const b = document.createElement("button");
  b.className = "btn act-btn";
  b.textContent = "Actions ▾";
  b.title = "Actions for " + e.name;
  b.setAttribute("aria-haspopup", "menu");
  b.setAttribute("aria-expanded", "false");
  b.addEventListener("click", () => toggleMenu(b, items));
  return b;
}

// "YYYY-MM-DDTHH:MM:SS" -> "YYYY-MM-DD HH:MM" (the phone layout has no
// room for the seconds).
const shortTime = (mtime) => mtime.slice(0, 16).replace("T", " ");

export async function loadDir(path, fallbackToRoot = false) {
  path = normPath(path);
  const request = ++filesRequest;
  const requestedVolume = fbVol;
  $("fb-up").disabled = path === "/";
  $("fb-newbasic").hidden = !hasBasicEditor();
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Loading…";
  $("fb-rows").textContent = "";
  fbNames = new Set();

  let data;
  try {
    data = await api.listDir(path, requestedVolume);
  } catch (e) {
    if (request !== filesRequest || requestedVolume !== fbVol) return;
    if (fallbackToRoot && path !== "/" && e.status === 404) {
      history.replaceState(null, "", filesHash("/"));
      return loadDir("/");
    }
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could not list " + path + " — " + e.message;
    return;
  }

  if (request !== filesRequest || requestedVolume !== fbVol) return;
  const vol = data.vol || requestedVolume;
  fbVol = vol;
  fbPath = data.path || path;
  lastListingRequest = request;
  lastListingVolume = vol;
  // A successful listing is also evidence that its volume is browsable.
  if (!availableVolumes.includes(vol)) availableVolumes.push(vol);
  renderVolumeButtons();
  renderCrumbs(vol, fbPath);

  const entries = (data.entries || []).slice().sort((a, b) => {
    if (!!a.dir !== !!b.dir) return a.dir ? -1 : 1;
    return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
  });
  fbNames = new Set(entries.filter((e) => !e.dir).map((e) => e.name));

  const tbody = $("fb-rows");
  const frag = document.createDocumentFragment();
  for (const e of entries) {
    const childPath = normPath(path + "/" + e.name);
    const tr = document.createElement("tr");

    const tdName = document.createElement("td");
    tdName.className = "col-name";
    const wrap = document.createElement("span");
    wrap.className = "fname";
    const ic = createFileIcon(e.name, e.dir);
    wrap.appendChild(ic);
    let nm;
    if (e.dir) {
      nm = document.createElement("a");
      nm.href = filesHash(childPath);
      nm.textContent = e.name;
    } else if (tapeSelection && extOf(e.name) === "tap") {
      nm = nameLink(e.name, "Load Tape " + e.name, () => loadTape(childPath, e.name));
    } else if (extOf(e.name) === "rom" && machineName() === "C64") {
      nm = nameLink(e.name, "Load Raw Cartridge", () => loadRawCartridge(childPath, e));
    } else if (isRunnable(e.name)) {
      nm = nameLink(e.name, runVerb(e.name) + " " + e.name,
                    () => runFile(childPath, e.name));
    } else if (["d1m", "d2m", "d4m"].includes(extOf(e.name))) {
      nm = nameLink(e.name, "Mount " + e.name + " on drive 8",
                    () => mountDisk(childPath, e.name, 8));
    } else if (extOf(e.name) === "txt") {
      nm = nameLink(e.name, "View Text", () => openEditor({ vol: fbVol, path: childPath, name: e.name, readOnly: true }));
    } else if (e.edit) {
      nm = nameLink(e.name, "Edit " + e.name,
                    () => editFile(childPath, e.name));
    } else {
      nm = document.createElement("span");
      nm.textContent = e.name;
    }
    nm.classList.add("nm");
    wrap.appendChild(nm);
    tdName.appendChild(wrap);

    // Size and date sit under the name on a phone, where their own columns
    // are hidden.
    const meta = [e.dir ? "" : fmtBytes(e.size),
                  e.mtime ? shortTime(e.mtime) : ""].filter(Boolean).join(" · ");
    if (meta) {
      const sub = document.createElement("div");
      sub.className = "fmeta";
      sub.textContent = meta;
      tdName.appendChild(sub);
    }

    const tdSize = document.createElement("td");
    tdSize.className = "col-size";
    tdSize.textContent = e.dir ? "—" : fmtBytes(e.size);

    const tdMod = document.createElement("td");
    tdMod.className = "col-mod";
    tdMod.textContent = e.mtime ? e.mtime.replace("T", " ") : "";

    const tdAct = document.createElement("td");
    tdAct.className = "col-act";
    const actions = actionsButton(e, childPath);
    if (actions) tdAct.appendChild(actions);

    tr.append(tdName, tdSize, tdMod, tdAct);
    frag.appendChild(tr);
  }
  tbody.appendChild(frag);

  itemCount = !entries.length ? "Empty folder." : data.truncated ? entries.length + " entries (list truncated)." : entries.length + " item" + (entries.length === 1 ? "" : "s");
  restoreItemCount();
}

// Manual refresh only: no timers, remounts, or USB controller operations.
export async function refreshFiles() {
  const request = ++filesRequest;
  const volumeRequest = ++volumesRequest;
  const selected = fbVol;
  let path = pathFromHash();
  try {
    const result = await api.getVolumes();
    if (volumeRequest !== volumesRequest || request !== filesRequest ||
        selected !== fbVol || path !== pathFromHash()) return;
    rememberVolumes(result.volumes);
    availableVolumes = (result.volumes || []).map((v) => v.id);
    renderVolumeButtons();
  } catch (e) {
    if (request !== filesRequest || volumeRequest !== volumesRequest) return;
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could not refresh drives — " + e.message;
    return;
  }
  // Do not take over a newer folder/volume navigation while awaiting volumes.
  if (request !== filesRequest || selected !== fbVol || path !== pathFromHash()) return;
  if (!availableVolumes.length) {
    $("fb-rows").textContent = "";
    fbNames = new Set();
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "No available storage volumes.";
    return;
  }
  if (!availableVolumes.includes(fbVol)) {
    selectFilesVolume(availableVolumes.includes("USB") ? "USB" : availableVolumes[0]);
    localStorage.setItem("bmc64-files-volume", fbVol);
    path = "/";
    history.replaceState(null, "", filesHash(path));
  }
  await loadDir(path, true);
}

let itemCount = "";
function restoreItemCount() {
  $("fb-status").className = "msg";
  $("fb-status").textContent = "";
}

// ---- run (autostart) ----

async function loadRawCartridge(path, entry) {
  const vol = fbVol;
  const type = await chooseRawCartridge(entry.name, entry.size);
  if (!type) return;
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Loading Cartridge " + entry.name + "…";
  try {
    await api.loadRawCartridge(vol, path, type);
    restoreItemCount();
  } catch (error) {
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could Not Load Cartridge — " + error.message;
  }
}

async function runFile(path, name) {
  $("fb-status").className = "msg";

  try {
    await api.autostart(fbVol, path);
  } catch (e) {
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could not start " + name + " — " + e.message;
    return;
  }
  // Successful starts need no routine notification.
}

async function loadTape(path, name) {
  const selection = tapeSelection;
  if (selection?.busy) return;
  if (selection) selection.busy = true;
  const vol = fbVol;
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Attaching " + name + "…";
  try {
    await api.loadTape(vol, path);
    restoreItemCount();
    if (selection && tapeSelection === selection) {
      endTapeSelection();
      location.hash = "#/datasette";
    }
  } catch (error) {
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could not load tape " + name + " — " + error.message;
  } finally {
    if (selection) selection.busy = false;
  }
}

async function mountDisk(path, name, unit) {
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Mounting " + name + "…";
  try {
    await api.mountDisk(fbVol, path, unit);
    restoreItemCount();
  } catch (e) {
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could not mount " + name + " — " + e.message;
  }
}

async function loadPrg(path, name) {
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Loading " + name + "…";
  try {
    await api.loadPrg(fbVol, path);
    restoreItemCount();
  } catch (e) {
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could not load " + name + " — " + e.message;
  }
}

// ---- edit ----

async function editFile(path, name) {
  const result = await openEditor({ vol: fbVol, path, name });
  if (!result.saved) return;
  if (result.rebooting) {
    $("fb-status").className = "msg";
    restoreItemCount();
    return;
  }
  await loadDir(fbPath);
}

// ---- BASIC programs ----

// A BASIC program can't be bigger than the memory from its load address to
// the end of BASIC RAM ($A000), plus the two load address bytes.
const BASIC_FILE_MAX = 0xa000 - LOAD_ADDRESS + 2;

async function newBasic() {
  const result = await openBasicEditor({ vol: fbVol, dir: fbPath });
  await savedBasic(result);
}

async function editListing(path, e) {
  if (e.size > BASIC_FILE_MAX) {
    showError(e.name + " is too big to be a BASIC program.");
    return;
  }
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Reading " + e.name + "…";
  let parsed;
  try {
    parsed = parsePrg(new Uint8Array(await api.readFile(fbVol, path)));
  } catch (err) {
    showError("Could not read " + e.name + " — " + err.message);
    return;
  }
  if (!parsed) {
    showError(e.name + " is not a C64 BASIC program, so it has no listing to edit.");
    return;
  }
  restoreItemCount();
  const result = await openBasicEditor({
    vol: fbVol, dir: fbPath, path, name: e.name, parsed,
  });
  await savedBasic(result);
}

async function savedBasic(result) {
  if (!result.saved) return;
  await loadDir(fbPath);
}

// ---- delete ----

async function deleteEntry(path, name, isDir) {
  const question = isDir
    ? "Delete the folder “" + name + "” and everything in it?\n\n" +
      "Remove any disk image inside it first. This cannot be undone."
    : "Delete “" + name + "”?\n\nThis cannot be undone.";
  if (!await confirmE64(question)) return;
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Deleting " + name + "…";
  try {
    await api.deleteFile(fbVol, path, { recursive: isDir });
  } catch (e) {
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Could not delete " + name + " — " + e.message;
    return;
  }
  loadDir(fbPath);
}

// ---- new folder / rename ----

// A folder or file name is one path segment; the device checks the rest.
const hasSlash = (name) => /[\/\\]/.test(name);

function showError(text) {
  $("fb-status").className = "msg err";
  $("fb-status").textContent = text;
}

async function makeFolder() {
  const input = await promptE64("New Folder", "Enter the new folder name:", "", "Create", value => {
    const name = value.trim();
    if (!name) return "Enter a folder name.";
    return hasSlash(name) || /^\.+$/.test(name) ? "“" + name + "” is not a valid folder name." : "";
  });
  if (input === null) return;
  const name = input.trim();
  if (!name) return;
  if (hasSlash(name) || /^\.+$/.test(name)) {
    showError("“" + name + "” is not a valid folder name.");
    return;
  }
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Creating " + name + "…";
  try {
    await api.makeDir(fbVol, normPath(fbPath + "/" + name));
  } catch (e) {
    showError("Could not create " + name + " — " + e.message);
    return;
  }
  await loadDir(fbPath);
}

async function renameEntry(path, name) {
  const input = await promptE64("Rename", "Rename “" + name + "” to:", name, "Rename");
  if (input === null) return;
  const newName = input.trim();
  if (!newName || newName === name) return;
  if (hasSlash(newName) || /^\.+$/.test(newName)) {
    showError("“" + newName + "” is not a valid name.");
    return;
  }
  $("fb-status").className = "msg";
  $("fb-status").textContent = "Renaming " + name + "…";
  try {
    await api.renameEntry(fbVol, path, newName);
  } catch (e) {
    showError("Could not rename " + name + " — " + e.message);
    return;
  }
  await loadDir(fbPath);
}

// Browse mounted volumes and directories without making the user type a path.
function pickDestination(verb, name, isDir = false) {
  const kind = isDir ? "Folder" : "File";
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    const opener = document.activeElement;
    dialog.className = "e64-dialog destination-dialog";
    dialog.setAttribute("aria-label", verb + " " + kind);
    const header = createPopupHeader(verb + " " + kind, () => dialog.close());

    const makeLabel = (text) => {
      const el = document.createElement("div");
      el.textContent = text;
      el.className = "destination-label";
      return el;
    };

    const sourceLabel = makeLabel(kind + " to " + verb);

    const source = document.createElement("div");
    source.className = "destination-preview";
    const sourceName = document.createElement("span");
    sourceName.textContent = name;
    source.append(createFileIcon(name, isDir), sourceName);

    const pathLabel = makeLabel("Destination Folder");

    const preview = document.createElement("div");
    preview.className = "destination-preview";

    const current = document.createElement("button");
    current.className = "btn destination-current";
    current.disabled = true;
    current.addEventListener("click", () => {
      if (!valid) return;
      chosen = { vol, folder };
      dialog.close();
    });

    const folders = document.createElement("div");
    folders.className = "destination-folders";

    const message = document.createElement("div");
    message.className = "msg";

    const bar = document.createElement("div");
    bar.className = "destination-controls";

    const select = document.createElement("select");
    select.className = "btn";
    select.style.cssText =
      "width:230px;min-width:230px;max-width:230px;flex:0 0 230px;box-sizing:border-box;border-radius:9px;text-align:center";

    for (const volume of availableVolumes) {
      const option = document.createElement("option");
      option.value = volume;
      option.textContent = volumeLabel(volume);
      select.appendChild(option);
    }

    select.value = fbVol;

    const up = document.createElement("button");
    up.className = "btn";
    up.textContent = "↑ Up";
    up.style.cssText =
      "width:72px;min-width:72px;height:38px;" +
      "flex:0 0 72px;box-sizing:border-box;border-radius:9px";

    const spacer = document.createElement("span");
    spacer.style.flex = "1";

    const choose = document.createElement("button");
    choose.className = "btn btn-primary";
    choose.textContent = verb;
    choose.style.cssText =
      "width:72px;min-width:72px;height:38px;" +
      "flex:0 0 72px;box-sizing:border-box;border-radius:9px";

    const cancel = document.createElement("button");
    cancel.className = "btn";
    cancel.textContent = "Cancel";
    cancel.style.cssText =
      "width:72px;min-width:72px;height:38px;" +
      "flex:0 0 72px;box-sizing:border-box;border-radius:9px";

    bar.append(select, up, spacer, choose, cancel);

    dialog.append(
      header,
      sourceLabel,
      source,
      pathLabel,
      preview,
      current,
      folders,
      bar
    );

    document.body.appendChild(dialog);

    let vol = fbVol;
    let folder = "/";
    let valid = false;
    let chosen = null;
    let requestId = 0;

    const displayVol = volumeLabel;

    function folderButton(entry) {
      const button = document.createElement("button");
      button.className = "btn";
      const label = document.createElement("span");
      label.textContent = entry.name;
      button.append(createFileIcon(entry.name, true), label);
      button.style.cssText =
        "text-align:left;flex-shrink:0;" +
        "min-height:38px;width:100%";

      button.addEventListener("click", () => {
        folder = normPath(folder + "/" + entry.name);
        refresh();
      });

      folders.appendChild(button);
    }

    async function refresh() {
      const request = ++requestId;

      valid = false;
      choose.disabled = true;
      current.disabled = true;
      current.textContent = (folder === "/" ? verb + " to the root of: " : "Use this directory: ") + displayVol(vol) + ":" + folder;
      up.disabled = folder === "/";
      up.style.borderColor = up.disabled ? "var(--border)" : "var(--blue)";
      up.style.color = up.disabled ? "var(--muted)" : "var(--fg)";

      preview.textContent =
        displayVol(vol) + ":" + normPath(folder + "/" + name);

      folders.textContent = "";

      message.textContent = "Loading folders…";
      folders.appendChild(message);

      try {
        const data = await api.listDir(folder, vol);

        if (request !== requestId) return;

        valid = true;
        choose.disabled = false;
        current.disabled = false;
        folders.textContent = "";

        const entries = (data.entries || [])
          .filter((entry) => entry.dir || !/^readme/i.test(entry.name))
          .sort((a, b) => {
            if (a.dir !== b.dir) return a.dir ? -1 : 1;
            return a.name.localeCompare(b.name);
          });

        for (const entry of entries) {
          if (entry.dir) {
            folderButton(entry);
          } else {
            const file = document.createElement("div");
            const label = document.createElement("span");
            label.textContent = entry.name;
            file.append(createFileIcon(entry.name, false), label);
            file.className = "destination-file";
            folders.appendChild(file);
          }
        }

        if (!entries.length) {
          message.textContent =
            "You can " + verb.toLowerCase() +
            " this " + kind.toLowerCase() + " to this location.";
          folders.appendChild(message);
        }

      } catch (e) {
        if (request !== requestId) return;

        folders.textContent = "";
        message.textContent =
          "Cannot open folder: " + e.message;
        folders.appendChild(message);
      }
    }

    select.addEventListener("change", () => {
      vol = select.value;
      folder = "/";
      refresh();
    });

    up.addEventListener("click", () => {
      if (folder === "/") return;
      folder = parentPath(folder);
      refresh();
    });

    choose.addEventListener("click", () => {
      if (!valid) return;

      chosen = { vol, folder };
      dialog.close();
    });

    cancel.addEventListener("click", () => {
      dialog.close();
    });

    dialog.addEventListener("close", () => {
      dialog.remove();
      if (opener?.isConnected !== false) opener?.focus();
      resolve(chosen);
    }, { once: true });

    dialog.showModal();
    refresh();
  });
}

async function transferEntry(path, name, move, isDir = false) {
  const verb = move ? "Move" : "Copy";
  const dest = await pickDestination(verb, name, isDir);
  if (!dest) return;
  const destVol = dest.vol;
  const destPath = normPath(dest.folder + "/" + name);
  try {
    if (destVol === fbVol && destPath === path) {
      showError("Choose a different destination folder.");
      return;
    }
    $("fb-status").className = "msg";
    $("fb-status").textContent =
      (move ? "Moving " : "Copying ") + name + "…";
    // Use the explicit root-folder form; the backend appends the source name.
    await api.transferEntry(fbVol, path, destVol, dest.folder === "/" ? "/" : destPath, move);
    await loadDir(fbPath);
  } catch (e) {
    showError(verb + " failed: " + e.message);
  }
}

// ---- upload ----

function uploadOne(file, overwrite) {
  return api.upload(fbVol, normPath(fbPath + "/" + file.name), file, {
    overwrite,
    onProgress: (frac) => {
      $("fb-status").textContent =
        "Uploading " + file.name + " — " + Math.round(frac * 100) + "%";
    },
  });
}

// Returns "ok" or "skipped"; throws on real failure.
async function uploadWithRetry(file, overwrite) {
  try {
    await uploadOne(file, overwrite);
    return "ok";
  } catch (e) {
    if (e.conflict && !overwrite) {
      if (!await confirmE64("“" + file.name + "” already exists here. Overwrite it?")) {
        return "skipped";
      }
      await uploadOne(file, true);
      return "ok";
    }
    throw e;
  }
}

// Disables both ways in (the Upload… button and the sidebar drop zone)
// while an upload runs.
let uploading = false;

function setUploading(busy) {
  uploading = busy;
  $("fb-upload").disabled = busy;
  $("fb-upload-btn").classList.toggle("disabled", busy);
  $("fb-upload").value = "";
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length || uploading) return;

  const clashes = files.filter((f) => fbNames.has(f.name));
  if (clashes.length && !await confirmE64(
      "These file" + (clashes.length === 1 ? "" : "s") +
      " already exist here and will be overwritten:\n\n" +
      clashes.map((f) => f.name).join("\n") + "\n\nContinue?")) {
    $("fb-upload").value = "";
      return;
  }
  const overwriteNames = new Set(clashes.map((f) => f.name));

  setUploading(true);
  $("fb-status").className = "msg";
  let uploadError = "";
  for (const f of files) {
    try {
      await uploadWithRetry(f, overwriteNames.has(f.name));
    } catch (e) {
      $("fb-status").className = "msg err";
      uploadError = "Upload of " + f.name + " failed — " + e.message;
      $("fb-status").textContent = uploadError;
      break;
    }
  }
  setUploading(false);
  await loadDir(fbPath);
  if (uploadError) showError(uploadError);
}

export function initFiles() {
  $("tape-load").addEventListener("click", beginTapeSelection);
  $("fb-tape-cancel").addEventListener("click", cancelTapeSelection);
  // Opening a config folder temporarily selects SD. Returning through the
  // normal Files navigation restores the user's saved storage preference.
  document.querySelector('.nav-item[data-view="files"]').addEventListener("click", () => {
    endTapeSelection();
    fbVol = "USB";
    // The hashchange handler reloads the root when navigation changes the URL.
    // If already at #/files, clicking Files must still reload the root.
    if (location.hash === filesHash("/")) loadDir("/");
  });
  for (const vol of STORAGE_VOLUMES) {
    $("fb-vol-" + vol).addEventListener("click", () => {
      if (!availableVolumes.includes(vol) || vol === fbVol) return;
      fbVol = vol;
      localStorage.setItem("bmc64-files-volume", vol);
      location.hash = filesHash("/");
      loadDir("/");
    });
  }
  const initialVolume = fbVol;
  const initialDirectoryRequest = filesRequest;
  const volumeRequest = ++volumesRequest;
  api.getVolumes().then((result) => {
    if (volumeRequest !== volumesRequest) return;
    rememberVolumes(result.volumes);
    availableVolumes = (result.volumes || []).map((v) => v.id);
    // The startup volume query can finish after a newer successful listing.
    // Do not replace that directory based on an older availability snapshot.
    if (lastListingRequest > initialDirectoryRequest && lastListingVolume === fbVol &&
        !availableVolumes.includes(fbVol)) availableVolumes.push(fbVol);
    if (fbVol === initialVolume && availableVolumes.length &&
        !availableVolumes.includes(fbVol)) {
      selectFilesVolume(availableVolumes.includes("USB") ? "USB" : availableVolumes[0]);
      localStorage.setItem("bmc64-files-volume", fbVol);
      if (location.hash.startsWith("#/files")) {
        history.replaceState(null, "", filesHash("/"));
        loadDir("/");
      }
    }
    renderVolumeButtons();
  }).catch(() => {
    if (volumeRequest === volumesRequest) renderVolumeButtons();
  });
  $("fb-up").addEventListener("click", () => {
    location.hash = filesHash(parentPath(pathFromHash()));
  });
  $("fb-refresh").addEventListener("click", refreshFiles);
  $("fb-mkdir").addEventListener("click", makeFolder);
  $("fb-newbasic").addEventListener("click", newBasic);
  $("fb-upload").addEventListener("change", (e) => uploadFiles(e.target.files));

  dropTarget($("fb-card"));
}

// Files dropped on `el` upload to the current folder. Only file drags are
// taken, so dragging text around the page doesn't light it up.
function dropTarget(el) {
  const isFiles = (e) => Array.from(e.dataTransfer.types || []).includes("Files");
  el.addEventListener("dragover", (e) => {
    if (!isFiles(e)) return;
    e.preventDefault();
    el.classList.add("over");
  });
  // dragleave also fires when moving onto a child; ignore that.
  el.addEventListener("dragleave", (e) => {
    if (!el.contains(e.relatedTarget)) el.classList.remove("over");
  });
  el.addEventListener("drop", (e) => {
    if (!isFiles(e)) return;
    e.preventDefault();
    el.classList.remove("over");
    uploadFiles(droppedFiles(e.dataTransfer));
  });
}

// Folders can't be uploaded; a dropped one shows up as a bogus empty file, so
// leave it out.
function droppedFiles(dt) {
  const items = Array.from(dt.items || []);
  if (!items.length || !items[0].webkitGetAsEntry) return dt.files;
  const files = [];
  let folders = 0;
  for (const item of items) {
    if (item.kind !== "file") continue;
    const entry = item.webkitGetAsEntry();
    if (entry && entry.isDirectory) { folders++; continue; }
    const f = item.getAsFile();
    if (f) files.push(f);
  }
  if (folders) {
    $("fb-status").className = "msg err";
    $("fb-status").textContent = "Folders can't be uploaded — skipped " + folders + ".";
  }
  return files;
}
