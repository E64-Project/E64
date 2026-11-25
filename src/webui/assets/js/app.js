import { initDatasette, setDatasetteVisible } from "./datasette.js";
import { initLogo } from "./logo.js";
import { initHelpNavigation } from "./help_dialog.js";
// Entry point: wires the modules together and switches between views.
//
//   api.js        every /api/* call
//   util.js       DOM lookup, formatting, path helpers
//   machine.js    the running machine and what the web UI can do on it
//   dashboard.js  status polling, hardware / storage meters, reboot & reset
//   files.js      Internal USB file browser
//   menu.js       pop-up menu for a file row's Actions button
//   editor.js     overlay editor for config files and BASIC listings
//   configs.js   the Configs page (configs_data.js reads the files)
//   basic.js      C64 BASIC V2 tokeniser / detokeniser (listing <-> PRG)

import { initAbout } from "./about.js";
import { showInstructions, hideInstructions } from "./instructions.js";
import { $ } from "./util.js";
import { initDashboard, refreshVolumes, startStatusPolling, syncDriveActivity } from "./dashboard.js";
import { initFiles, loadDir, filesHash, pathFromHash, endTapeSelection } from "./files.js";
import { initEditor } from "./editor.js";
import { initConfigs, loadConfigs } from "./configs.js";
import { loadMachine } from "./machine.js";

function route() {
  const hash = location.hash || "#/dashboard";
  const view = hash.startsWith("#/instructions") ? "instructions"
             : hash.startsWith("#/datasette") ? "datasette"
             : hash.startsWith("#/files") ? "files"
             : hash.startsWith("#/configs") ? "configs"
             : "dashboard";
  if (view !== "files") endTapeSelection();
  $("view-datasette").hidden = view !== "datasette";
  setDatasetteVisible(view === "datasette");
  $("view-instructions").hidden = view !== "instructions";
  $("view-dashboard").hidden = view !== "dashboard";
  syncDriveActivity();
  $("view-files").hidden = view !== "files";
  $("view-configs").hidden = view !== "configs";

  document.querySelectorAll(".nav-item[data-view]").forEach((el) => {
    el.classList.toggle("active", el.dataset.view === view);
  });

  if (view !== "instructions") hideInstructions();
  if (view === "instructions") {
    showInstructions(hash.split("/")[2]);
  } else if (view === "files") {
    loadDir(pathFromHash());
  } else if (view === "configs") {
    loadConfigs();
  } else if (view === "dashboard") {
    refreshVolumes();
  }
}

initDatasette();
initDashboard();
initAbout();
initLogo();
initHelpNavigation();
initFiles();
initEditor();
initConfigs();

window.addEventListener("hashchange", route);

// The file actions depend on the machine, so know it before the first view.
await loadMachine();
route();
startStatusPolling();
