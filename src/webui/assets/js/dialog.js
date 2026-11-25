// Shared native dialog shell: consistent header, Escape and focus restoration.
let nameFieldSerial = 0;
export function createPopupHeader(titleText, close) {
  const header = document.createElement("div");
  header.className = "e64-popup-header";
  const title = document.createElement("h2");
  title.textContent = titleText;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn popup-close";
  button.textContent = "Close";
  button.setAttribute("aria-label", "Close " + titleText);
  button.onclick = close;
  header.append(title, button);
  return header;
}
function shell(titleText) {
  const opener = document.activeElement;
  const dialog = document.createElement("dialog");
  dialog.className = "e64-dialog e64-confirm";
  dialog.setAttribute("aria-label", titleText);
  dialog.append(createPopupHeader(titleText, () => dialog.close()));
  dialog.addEventListener("cancel", event => { event.preventDefault(); dialog.close(); });
  const finish = callback => dialog.addEventListener("close", () => {
    dialog.remove();
    if (opener?.isConnected !== false) opener?.focus();
    callback();
  }, { once: true });
  return { dialog, finish };
}
export function confirmE64(message, accept = "Continue", cancelLabel = "Cancel") {
  return new Promise(resolve => {
    const lines = message.trim().split(/\n+/);
    const { dialog, finish } = shell(lines.shift());
    const text = document.createElement("p");
    text.textContent = lines.join("\n");
    const buttons = document.createElement("div");
    buttons.className = "dialog-buttons";
    const cancel = document.createElement("button");
    cancel.className = "btn"; cancel.textContent = cancelLabel;
    const ok = document.createElement("button");
    ok.className = "btn btn-primary"; ok.textContent = accept;
    cancel.onclick = () => dialog.close(); ok.onclick = () => dialog.close("accept");
    buttons.append(cancel, ok); dialog.append(text, buttons);
    finish(() => resolve(dialog.returnValue === "accept"));
    document.body.append(dialog); dialog.showModal(); cancel.focus();
  });
}
export function promptE64(title, instruction, initial = "", accept = "Save", validate = null) {
  return new Promise(resolve => {
    const { dialog, finish } = shell(title);
    const form = document.createElement("form");
    form.className = "e64-name-form";
    const label = document.createElement("label");
    label.textContent = instruction;
    const input = document.createElement("input");
    input.type = "text"; input.id = "e64-name-" + (++nameFieldSerial);
    input.value = initial; input.autocomplete = "off"; input.spellcheck = false;
    label.htmlFor = input.id;
    const error = document.createElement("p");
    error.className = "msg err"; error.setAttribute("role", "alert");
    const buttons = document.createElement("div"); buttons.className = "dialog-buttons";
    const cancel = document.createElement("button");
    cancel.type = "button"; cancel.className = "btn"; cancel.textContent = "Cancel";
    const create = document.createElement("button");
    create.type = "submit"; create.className = "btn btn-primary"; create.textContent = accept;
    let accepted = false, value = null;
    const submit = () => {
      const problem = validate ? validate(input.value) : "";
      error.textContent = problem || "";
      input.setAttribute("aria-invalid", String(Boolean(problem)));
      if (problem) { input.focus(); return; }
      value = input.value; accepted = true; dialog.close("accept");
    };
    form.addEventListener("submit", event => { event.preventDefault(); submit(); });
    input.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); submit(); }
    });
    cancel.onclick = () => dialog.close();
    buttons.append(cancel, create); form.append(label, input, error, buttons); dialog.append(form);
    finish(() => resolve(accepted && dialog.returnValue === "accept" ? value : null));
    document.body.append(dialog); dialog.showModal(); input.focus(); input.select?.();
  });
}
