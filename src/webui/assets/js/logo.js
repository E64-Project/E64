// Genuine C64 uppercase/graphics CHARGEN rows, screen codes $16 and $20-$39.
// Version comes from /api/status, which uses menu.c's authoritative VERSION_STRING.
const glyphs = {"V": [102, 102, 102, 102, 102, 60, 24, 0], " ": [0, 0, 0, 0, 0, 0, 0, 0], "0": [60, 102, 110, 118, 102, 102, 60, 0], "1": [24, 24, 56, 24, 24, 24, 126, 0], "2": [60, 102, 6, 12, 48, 96, 126, 0], "3": [60, 102, 6, 28, 6, 102, 60, 0], "4": [6, 14, 30, 102, 127, 6, 6, 0], "5": [126, 96, 124, 6, 6, 102, 60, 0], "6": [60, 102, 96, 124, 102, 102, 60, 0], "7": [126, 102, 12, 24, 24, 24, 24, 0], "8": [60, 102, 102, 60, 102, 102, 60, 0], "9": [60, 102, 102, 62, 6, 102, 60, 0], ".": [0, 0, 0, 0, 0, 24, 24, 0]};
export function updateLogoVersion(version) {
  const button = document.getElementById("logo-toggle");
  if (!button) return;
  const match = /^(\d+(?:\.\d+)*)/.exec(String(version || ""));
  if (!match) return;
  const text = "V " + match[1];
  const canvas = document.getElementById("logo-version-text");
  if (canvas.dataset.version === text) return;
  canvas.dataset.version = text;
  canvas.width = text.length * 8;
  canvas.height = 8;
  canvas.setAttribute("aria-label", text);
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, 8);
  ctx.fillStyle = "#0000FF";
  for (let i = 0; i < text.length; i++)
    for (let y = 0; y < 8; y++)
      for (let x = 0; x < 8; x++)
        if (glyphs[text[i]][y] & (128 >> x)) ctx.fillRect(i * 8 + x, y, 1, 1);
}
export function initLogo() {
  const button = document.getElementById("logo-toggle");
  button.addEventListener("click", () => {
    const panel = document.getElementById("logo-version");
    panel.hidden = !panel.hidden;
    button.setAttribute("aria-pressed", String(!panel.hidden));
    button.setAttribute("aria-label", panel.hidden ? "Show version" : "Show rainbow bars");
  });
}
