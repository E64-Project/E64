import { showHelp } from "./help_dialog.js";
// About is informational; sidebar navigation remains available.
// The native GPL remains in third_party/common/text.c; do not duplicate it here.
export function initAbout() {
  const button = document.getElementById("about-e64-button");
  const popup = document.getElementById("about-e64-popup");
  button.addEventListener("click", () => {
    if (!popup.open) showHelp(popup);
    popup.querySelector("button").focus();
  });
  popup.addEventListener("cancel", (event) => {
    event.preventDefault();
    popup.close();
  });
  popup.addEventListener("close", () => {
    if (!popup.dataset.helpNavigating && button.isConnected) button.focus();
  });
}
