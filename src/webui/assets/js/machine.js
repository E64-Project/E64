import { updateLogoVersion } from "./logo.js";
// The machine BMC64 is running and what the web UI can do on it, from the
// "machine" and "caps" of /api/status (webui_machine.cpp on the device).

import * as api from "./api.js";
import { machineLabel } from "./configs_data.js";

// Nothing is offered until the device has answered.
let current = { name: "", run: new Set(), basic: "" };

// Takes the machine from a /api/status answer.
export function setMachine(status) {
  updateLogoVersion(status?.version);
  const caps = (status && status.caps) || {};
  current = {
    name: (status && status.machine) || "",
    run: new Set((caps.run || []).map((t) => String(t).toLowerCase())),
    basic: caps.basic || "",
  };
}

// Asks the device once; on failure the status polling fills it in later.
export async function loadMachine() {
  try {
    setMachine(await api.getStatus());
  } catch (e) {
    /* keep what we have */
  }
}

// C64 machine name as configs use it.
export const machineName = () => current.name;

// C64 name for display.
export const machineDisplayName = () => machineLabel(current.name) || "machine";

// Whether Autostart accepts files with this extension.
export const canRun = (ext) => current.run.has(String(ext).toLowerCase());

// Whether the BASIC listing editor works on this machine.
export const hasBasicEditor = () => current.basic !== "";
