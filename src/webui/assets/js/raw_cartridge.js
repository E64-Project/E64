import { createPopupHeader } from "./dialog.js";
import { fmtBytes } from "./util.js";
let serial = 0;
export function rawCartridgeTypes(size) {
  if (!Number.isInteger(size) || size < 0 || size > 16386) return [];
  const payload = size - ((size & 2) ? 2 : 0);
  return [
    ["8k", [4096, 8192]], ["16k", [12288, 16384]],
    ["ultimax", [4096, 12288, 16384]],
  ].filter(([, sizes]) => sizes.includes(payload)).map(([type]) => type);
}
export function chooseRawCartridge(name, size) {
  return new Promise(resolve => {
    const opener = document.activeElement;
    const dialog = document.createElement("dialog");
    dialog.className = "e64-dialog e64-confirm raw-cartridge-dialog";
    dialog.setAttribute("aria-label", "Load Raw Cartridge");
    const close = () => dialog.close();
    dialog.append(createPopupHeader("Load Raw Cartridge", close));
    const form = document.createElement("form"); form.className = "e64-name-form";
    const file = document.createElement("div"); file.className = "raw-cartridge-file";
    const filename = document.createElement("span"); filename.textContent = name;
    const fileSize = document.createElement("span"); fileSize.textContent = fmtBytes(size);
    file.append(filename, fileSize);
    const note = document.createElement("div"); note.className = "raw-cartridge-notes";
    for (const warning of ["For cartridge ROMs only.\nSize does not identify cartridge type.",
                           "Loading replaces the attached cartridge.\nA failed load may detach it."]) {
      const paragraph = document.createElement("p"); paragraph.textContent = warning; note.append(paragraph);
    }
    const label = document.createElement("label"); label.textContent = "Cartridge Type";
    const select = document.createElement("select"); select.id = "raw-cart-type-" + (++serial); label.htmlFor = select.id;
    const allowed = rawCartridgeTypes(size);
    for (const [value, text] of [["", "Select Cartridge Type"], ["8k", "8K Raw"], ["16k", "16K Raw"], ["ultimax", "Ultimax Raw"]]) {
      const option = document.createElement("option"); option.value = value; option.textContent = text;
      option.disabled = Boolean(value && !allowed.includes(value)); select.append(option);
    }
    // Suggest conventional mapping, never Ultimax. Confirmation still required.
    select.value = allowed.includes("8k") ? "8k" : allowed.includes("16k") ? "16k" : "";
    const error = document.createElement("p"); error.className = "msg err"; error.setAttribute("role", "alert");
    if (!allowed.length) error.textContent = "Unsupported Raw Cartridge Size";
    const buttons = document.createElement("div"); buttons.className = "dialog-buttons";
    const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "btn"; cancel.textContent = "Cancel"; cancel.onclick = close;
    const load = document.createElement("button"); load.type = "submit"; load.className = "btn btn-primary"; load.textContent = "Load & Run"; load.disabled = !allowed.length;
    let chosen = null;
    form.addEventListener("submit", event => {
      event.preventDefault();
      if (!allowed.includes(select.value)) { error.textContent = "Select A Compatible Cartridge Type"; select.focus(); return; }
      chosen = select.value; dialog.close("accept");
    });
    dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
    dialog.addEventListener("close", () => {
      dialog.remove(); if (opener?.isConnected !== false) opener?.focus();
      resolve(dialog.returnValue === "accept" ? chosen : null);
    }, { once: true });
    const typeField = document.createElement("div"); typeField.className = "raw-cartridge-type";
    typeField.append(label, select);
    buttons.append(cancel, load); form.append(file, note, typeField, error, buttons); dialog.append(form);
    document.body.append(dialog); dialog.showModal(); cancel.focus();
  });
}
