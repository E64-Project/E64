// Only informational surfaces use this helper. Editors and confirmations keep their existing modal behavior.
const helpIds = ["instructions-popup", "jiffydos-commands-popup", "about-e64-popup"];
export function showHelp(popup) {
  if (!popup.dataset.helpReady) {
    popup.addEventListener("keydown", event => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); popup.close(); }
    });
    popup.dataset.helpReady = "true";
  }
  popup.dataset.helpNavigating = "";
  popup.show();
  popup.querySelector("button:not([hidden])")?.focus();
}
export function initHelpNavigation() {
  document.addEventListener("keydown", event => {
    if (event.key !== "Escape" || event.defaultPrevented || document.querySelector("dialog:modal")) return;
    for (const id of [...helpIds].reverse()) {
      const popup = document.getElementById(id);
      if (popup?.open && !popup.hidden) {
        event.preventDefault(); popup.close(); return;
      }
    }
  });
  for (const link of document.querySelectorAll(".sidebar .nav-item[data-view]")) {
    link.addEventListener("click", () => {
      for (const id of helpIds) {
        const popup = document.getElementById(id);
        if (popup?.open) { popup.dataset.helpNavigating = "true"; popup.onclose = null; popup.close(); }
      }
      // Close handlers may restore an opener; leave focus on the chosen route.
      queueMicrotask(() => link.focus());
    });
  }
}
