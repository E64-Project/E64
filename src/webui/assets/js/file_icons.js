// Visual classification only: operations/capabilities remain in files.js.
// Directory metadata always wins. Ambiguous .bin/.img and extensionless files
// deliberately remain generic. Colors match the project's Godot C64 palette.
export const FILE_ICON_TYPES = Object.freeze({
  directory: ["folder", "Directory"], floppy: ["floppy", "Floppy disk image"],
  harddisk: ["hard-drive", "Hard disk image"], cartridge: ["cartridge", "Cartridge image"],
  tape: ["cassette", "Tape image"], program: ["program", "Program file"],
  snapshot: ["snapshot", "Snapshot"], rom: ["rom", "ROM image"], unknown: ["file", "File"],
});
const extensions = Object.freeze({
  d64: "floppy", d71: "floppy", d81: "floppy", g64: "floppy", d67: "floppy", d80: "floppy", d82: "floppy",
  d1m: "floppy", d2m: "floppy", d4m: "floppy",
  dhd: "harddisk", crt: "cartridge", tap: "tape", t64: "tape", prg: "program", p00: "program", vsf: "snapshot", rom: "rom",
});
export function fileIconType(name, isDirectory) {
  if (isDirectory) return "directory";
  const base = String(name ?? "").split(/[\\/]/).pop();
  const dot = base.lastIndexOf(".");
  const extension = dot > 0 ? base.slice(dot + 1).toLowerCase() : "";
  return Object.hasOwn(extensions, extension) ? extensions[extension] : "unknown";
}
export function createFileIcon(name, isDirectory) {
  const type = fileIconType(name, isDirectory);
  const [asset, label] = FILE_ICON_TYPES[type];
  const icon = document.createElement("img");
  icon.className = "ic file-type-icon " + (isDirectory ? "dir" : "file");
  icon.dataset.fileType = type;
  icon.setAttribute("src", "/icons/" + asset + ".svg");
  icon.setAttribute("width", "16");
  icon.setAttribute("height", "16");
  icon.setAttribute("alt", label);
  icon.setAttribute("title", label);
  return icon;
}
