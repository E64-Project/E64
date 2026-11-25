// Reading the config files in /configs (docs/CONFIGS.md, Config files)
// the same way the device does (src/configs). Plain functions with no DOM,
// so tools/webui_test can run them under Node.js.

import { MAX_CONFIG_NAME } from "./config_limits.js";
export { MAX_CONFIG_NAME } from "./config_limits.js";

export const DEFAULT_ID = "_factory-ntsc";
export const FACTORY_CONFIGS = [
 {id:DEFAULT_ID, name:"Default", machine:"C64/NTSC", start:"switch", category:"", disks:[], autostart:"", factory:true},
];
// The retired PAL identity remains readable/protected for old selections only.
export const isFactory = id => id === DEFAULT_ID || id === "_factory-pal";
export const FIRST_DRIVE = 8;
export const NUM_DRIVES = 4;

const MAX_ID = 32;
const MAX_NAME = MAX_CONFIG_NAME;
const MAX_CATEGORY = 32;
const MAX_DESCRIPTION = 64;
const MAX_MACHINE = 128;
const MAX_PATH = 256;

// key=value lines: '#' starts a comment line, spaces around keys and values
// are ignored, Windows line endings are accepted, and the last of a repeated
// key wins.
export function parseKv(text) {
  const values = new Map();
  for (const raw of String(text).split("\n")) {
    const line = raw.replace(/^[ \t\r]+|[ \t\r]+$/g, "");
    const equals = line.indexOf("=");
    if (line.startsWith("#") || equals < 0) continue;
    const key = line.slice(0, equals).replace(/[ \t\r]+$/, "");
    if (!key) continue;
    values.set(key, line.slice(equals + 1).replace(/^[ \t\r]+/, ""));
  }
  return values;
}

// 1 to 32 lowercase letters, digits and '-'.
export function idValid(id) {
  if (isFactory(id)) return true;
  return typeof id === "string" && id !== "main" && id.length > 0 && id.length <= MAX_ID &&
         /^[a-z0-9-]+$/.test(id);
}

const cut = (value, max) => (value || "").slice(0, max);

// The startup disks (disk_8 … disk_11) and autostart of a config.txt or of
// the user Config metadata.
function startupActions(values) {
  const disks = [];
  for (let i = 0; i < NUM_DRIVES; i++) {
    disks.push(cut(values.get("disk_" + (FIRST_DRIVE + i)), MAX_PATH));
  }
  return { disks, autostart: cut(values.get("autostart"), MAX_PATH) };
}

// A config from its id (folder name) and config.txt text, or null if it
// isn't a valid config (it needs a name and a machine).
export function parseConfig(id, text) {
  const values = parseKv(text);
  const name = values.get("name") || "";
  if (new TextEncoder().encode(name).length > MAX_NAME) return null;
  const machine = cut(values.get("machine"), MAX_MACHINE);
  if (!idValid(id) || !name || !machine) return null;
  return {
    id,
    name,
    machine,
    category: cut(values.get("category"), MAX_CATEGORY),
    description: cut(values.get("description"), MAX_DESCRIPTION),
    start: values.get("start") === "once" ? "once" : "switch",
    ...startupActions(values),
  };
}

// Persistent and one-time selections. Invalid identities use NTSC.
export function parseActive(text) {
  const values = parseKv(text);
  const config = values.get("config");
  const once = values.get("once");
  return {
    config: idValid(config) ? config : DEFAULT_ID,
    once: idValid(once) ? once : "",
  };
}

const MACHINE_LABELS = {};

// The parts of a machine value: machine / standard / output / description
// (the description may hold '/' itself).
function machineParts(machine) {
  const parts = String(machine || "").split("/");
  const head = parts.slice(0, 3);
  if (parts.length > 3) head.push(parts.slice(3).join("/"));
  return head.map((p) => p.trim()).filter((p, i) => p || i === 0);
}

// Short C64 machine name for display.
export function machineLabel(machine) {
  const name = machineParts(machine)[0] || "";
  return MACHINE_LABELS[name.toLowerCase()] || name;
}

// The rest of a machine value for display, e.g. "PAL · HDMI".
export function machineDetail(machine) {
  return machineParts(machine).slice(1).join(" · ").replace(/\s*@\s*/g, " @ ").replace(/\s*Hz\b/g, " Hz");
}

// Configs sorted by name as the menu lists them, grouped by category:
// those without a category first, then each category in the order its
// first config appears.
export function groupConfigs(configs) {
  const lower = (s) => s.replace(/[A-Z]/g, (c) => c.toLowerCase());
  const sorted = configs.slice().sort((a, b) => {
    const x = lower(a.name);
    const y = lower(b.name);
    return x < y ? -1 : x > y ? 1 : 0;
  });
  const groups = [{ category: "", configs: [] }];
  for (const p of sorted) {
    let group = groups.find((g) => g.category === p.category);
    if (!group) {
      group = { category: p.category, configs: [] };
      groups.push(group);
    }
    group.configs.push(p);
  }
  return groups.filter((g) => g.configs.length);
}

export function baseName(path) {
  const s = String(path || "");
  return s.slice(s.lastIndexOf("/") + 1);
}

// ---- Rename and delete, as the menu does them ----

// A new or renamed name: spaces trimmed, at most MAX_CONFIG_NAME UTF-8 bytes, on
// one line. "" if nothing is left.
export function cleanName(input) {
  const name = String(input || "").replace(/^ +/, "")
    .replace(/[\r\n]/g, " ");
  const clean = name.replace(/ +$/, "");
  return new TextEncoder().encode(clean).length <= MAX_CONFIG_NAME ? clean : "";
}

// The key of a key=value line, or "" for comments and other lines.
function lineKey(line) {
  const trimmed = line.replace(/^[ \t\r]+/, "");
  const equals = trimmed.indexOf("=");
  if (trimmed.startsWith("#") || equals < 0) return "";
  return trimmed.slice(0, equals).replace(/[ \t\r]+$/, "");
}

function lineValue(line) {
  return line.slice(line.indexOf("=") + 1).replace(/^[ \t\r]+|[ \t\r]+$/g, "");
}

// Rewrites a file's lines with edit(line, key), which returns the new line
// or null to drop it. Keeps the file's line endings.
function editLines(text, edit) {
  const eol = /\r\n/.test(text) ? "\r\n" : "\n";
  const lines = String(text).split(/\r?\n/);
  if (lines[lines.length - 1] === "") lines.pop();
  const out = [];
  for (const line of lines) {
    const changed = edit(line, lineKey(line));
    if (changed !== null) out.push(changed);
  }
  return out.length ? out.join(eol) + eol : "";
}

// config.txt text with its name changed; everything else is kept.
export function withName(text, name) {
  const valid = cleanName(name);
  if (!valid || valid !== name) throw new Error("Invalid Config name");
  let named = false;
  const result = editLines(text, (line, key) => {
    if (key !== "name") return line;
    if (named) return null;
    named = true;
    return "name=" + name;
  });
  return named ? result : "name=" + name + (/\r\n/.test(text) ? "\r\n" : "\n") + result;
}

// active.txt text once config id is deleted: Default NTSC starts at power-on
// instead of it, and a pending Start once of it is dropped. null if active.txt
// doesn't mention it.
export function activeWithout(text, id) {
  let changed = false;
  const result = editLines(text, (line, key) => {
    if (lineValue(line) !== id) return line;
    if (key === "config") {
      changed = true;
      return "config=" + DEFAULT_ID;
    }
    if (key === "once") {
      changed = true;
      return null;
    }
    return line;
  });
  return changed ? result : null;
}

// A config keeps C64 settings only.
const SETTINGS_MACHINES = ["c64"];

export function settingsFile(machine) {
  const name = String(machine || "").split("/")[0].trim().toLowerCase();
  return SETTINGS_MACHINES.includes(name) ? "settings-" + name + ".txt" : "settings.txt";
}

// The files the menu's Delete removes from a config's folder (and the
// backups the web UI's editor makes). Anything else in the folder is kept,
// and then so is the folder.
const OWN_FILES = ["config.txt", "vice.ini", "settings.txt",
                   ...SETTINGS_MACHINES.map((m) => "settings-" + m + ".txt")];
export const CONFIG_FILES = [
  ...OWN_FILES, "vice.in~", ...OWN_FILES.map((f) => f + ".bak"),
];

// Video standard is only the saved machine's explicit second component.
// Names and machine-only legacy records are never used to guess a standard.
export function configVideoStandard(machine) {
  const standard = String(machine || "").split("/")[1]?.trim().toUpperCase();
  return standard === "PAL" || standard === "NTSC" ? standard : "";
}
