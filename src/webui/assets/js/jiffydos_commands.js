import { showHelp } from "./help_dialog.js";
// Exact command/description reference supplied by the user from JiffyDOS v6.01.
// This popup only displays reference text; it never executes commands.
const commands = {
  disk: [
    ["@", "Drive status"], ["@$", "Directory"],
    ["@#", "Set default device"], ["CTRL+D", "Change default device"],
    ["@I", "Initialize drive"], ["@UJ", "Reset drive"],
    ["@V", "Validate disk"], ["@N", "Format disk"],
    ["@B", "Disable 1541 head rattle"],
  ],
  files: [
    ["@R", "Rename"], ["@S", "Scratch (delete)"],
    ["@C", "Copy on same disk"], ["@L", "Lock/unlock"],
    ["@D", "List BASIC file"], ["@T", "List text file"],
    ["@O", "Un-NEW BASIC"],
  ],
  programs: [
    ["/file", "Load BASIC"], ["↑file", "Load and run BASIC"],
    ["←file", "Save BASIC"], ["%file", "Load machine language"],
    ["£file", "Load and run machine language"],
    ["SHIFT+RUN/STOP", "Load and run first disk program"],
  ],
  advanced: [
    ["@G", "Set interleave"], ["@P", "Toggle printer output"],
    ["CTRL+P", "Print screen"], ["@F", "Disable function keys"],
    ["@Q", "Disable commands"], ["@X", "Destination device"],
    ["CTRL+A", "Toggle all files for copy"],
    ["CTRL+W", "Toggle one file for copy"],
    ["SYS 58451", "Re-enable commands"],
    ["SYS 58551", "Re-enable commands and function keys"],
  ],
};
let opener = null;
function selectTab(popup, key, focus = false) {
  if (!Object.hasOwn(commands, key)) return;
  const tabs = popup.querySelectorAll('[role="tab"]');
  for (const tab of tabs) {
    const selected = tab.dataset.commandTab === key;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
  }
  document.getElementById("jiffy-command-panel").setAttribute("aria-labelledby", "jiffy-tab-" + key);
  const rows = document.getElementById("jiffy-command-rows");
  rows.replaceChildren();
  for (const [command, description] of commands[key]) {
    const row = document.createElement("tr");
    const commandCell = document.createElement("td");
    const code = document.createElement("code");
    code.textContent = command;
    commandCell.append(code);
    const descriptionCell = document.createElement("td");
    descriptionCell.textContent = description;
    row.append(commandCell, descriptionCell);
    rows.append(row);
  }
  popup.scrollTop = 0;
}
export function openJiffyCommands(button) {
  const popup = document.getElementById("jiffydos-commands-popup");
  if (!popup) return;
  opener = button || document.activeElement;
  if (!popup.dataset.initialized) {
    const tabs = Array.from(popup.querySelectorAll('[role="tab"]'));
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectTab(popup, tab.dataset.commandTab));
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (index + tabs.length - 1) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        selectTab(popup, tabs[next].dataset.commandTab, true);
      });
    });
    popup.addEventListener("close", () => {
      if (!popup.dataset.helpNavigating && opener?.isConnected) opener.focus();
      opener = null;
    });
    popup.dataset.initialized = "true";
  }
  selectTab(popup, "disk");
  if (!popup.open) showHelp(popup);
  popup.querySelector('[role="tab"][aria-selected="true"]').focus();
}
export function closeJiffyCommands() {
  const popup = document.getElementById("jiffydos-commands-popup");
  if (popup?.open) popup.close();
}
