// Every call to the device's /api/* endpoints lives here, so the other
// modules deal only in plain values and ApiError.

export class ApiError extends Error {
  constructor(status, detail) {
    super(status === 401
      ? "authentication required — reload the page and enter the PIN"
      : "HTTP " + status + (detail ? " " + detail : ""));
    this.status = status;
  }
}

async function check(r) {
  if (!r.ok) throw new ApiError(r.status, (await r.text()).trim());
  return r;
}

async function getJson(url, signal) {
  return (await check(await fetch(url, { cache: "no-store", signal }))).json();
}

async function post(url, init) {
  await check(await fetch(url, { method: "POST", ...init }));
}

const fsQuery = (vol, path) =>
  "vol=" + encodeURIComponent(vol) + "&path=" + encodeURIComponent(path);

// Required by the device on every call that changes the card's config or
// layout (see webui.cpp); it keeps other sites from triggering them.
const WEB_HEADER = { "X-BMC64-Web": "1" };

// ---- status ----

export const getDriveActivity = (signal) => getJson("/api/drive-activity", signal);
export const getStatus = () => getJson("/api/status");
export const getVolumes = (capacity = false) =>
  getJson("/api/volumes" + (capacity ? "?capacity=1" : ""));

export const reboot = () => post("/api/reboot", { headers: WEB_HEADER });
export const shutdown = () => post("/api/shutdown", { headers: WEB_HEADER });
export const hardReset = () =>
  post("/api/reset", { headers: WEB_HEADER });
export const softReset = () =>
  post("/api/reset/soft", { headers: WEB_HEADER });
export const toggleWarp = () =>
  post("/api/warp/toggle", { headers: WEB_HEADER });
export const swapJoysticks = () =>
  post("/api/joysticks/swap", { headers: WEB_HEADER });
export const disableWebUi = () => post("/api/webui/disable");

// Switch to (or, with `once`, Start once) a config; BMC64 restarts into it.
export const startConfig = (id, once) =>
  post("/api/configs/start?id=" + encodeURIComponent(id) + "&once=" + (once ? 1 : 0),
       { headers: WEB_HEADER });

// Permanent Config deletion is guarded on the emulator thread, not by the
// generic file-manager delete endpoint. Only the second Yes reaches here.
export const getDeletedConfigs = () => getJson("/api/configs/deleted");
export const deleteConfigPermanent = (id, legacy = false) =>
  post("/api/configs/deleted?id=" + encodeURIComponent(id) + "&permanent=1&confirmed=1&legacy=" + (legacy ? 1 : 0),
       { headers: WEB_HEADER });

// ---- files ----

// No vol: the first listing tells us which volume the device uses.
export async function listDir(path, vol = "") {
  const data = await getJson("/api/fs/list?path=" + encodeURIComponent(path) +
                            (vol ? "&vol=" + encodeURIComponent(vol) : ""));
  // Streaming responses can encounter a filesystem failure after HTTP headers.
  if (data.error) throw new ApiError(data.error_status || 503, data.error);
  return data;
}

export const downloadUrl = (vol, path) =>
  "/api/fs/download?" + fsQuery(vol, path);

// The file's bytes, as an ArrayBuffer.
export async function readFile(vol, path, maxBytes = Infinity) {
  const r = await check(await fetch(downloadUrl(vol, path), { cache: "no-store" }));
  if (Number(r.headers.get("Content-Length")) > maxBytes) {
    await r.body?.cancel();
    throw new Error("File exceeds the 256 KB text limit. Download it to open locally.");
  }
  if (!Number.isFinite(maxBytes)) return r.arrayBuffer();
  const reader = r.body.getReader(), chunks = [];
  let length = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > maxBytes) throw new Error("File exceeds the 256 KB text limit. Download it to open locally.");
      chunks.push(value);
    }
  } catch (error) { await reader.cancel(); throw error; }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return bytes.buffer;
}

// With `recursive`, a folder is deleted together with everything in it.
export const deleteFile = (vol, path, { recursive = false } = {}) =>
  post("/api/fs/delete?" + fsQuery(vol, path) + (recursive ? "&recursive=1" : ""),
       recursive ? { headers: WEB_HEADER } : undefined);

export const autostart = (vol, path) =>
  post("/api/fs/autostart?" + fsQuery(vol, path));

// This operation has its own completion result; a queued request is not success.
export async function loadRawCartridge(vol, path, type) {
  const reply = await check(await fetch("/api/fs/raw-cartridge?" + fsQuery(vol, path) +
    "&type=" + encodeURIComponent(type) + "&replace=1", { method: "POST", headers: WEB_HEADER }));
  const { request_id: id } = await reply.json();
  if (!Number.isInteger(id) || id <= 0) throw new Error("Invalid Cartridge Request ID");
  for (let attempt = 0; attempt < 150; attempt++) {
    const result = await getJson("/api/fs/raw-cartridge?id=" + id);
    if (result.request_id !== id) throw new Error("Cartridge Request Changed");
    if (result.state === 3) return;
    if (result.state === 4) throw new Error(result.error || "Cartridge Attachment Failed");
    if (result.state !== 1 && result.state !== 2) throw new Error("Invalid Cartridge Request State");
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error("Completion Not Confirmed; The Request May Still Complete");
}

export const mountDisk = (vol, path, unit = 8) =>
  post("/api/fs/mount?" + fsQuery(vol, path) + "&unit=" + unit);

export const loadPrg = (vol, path) =>
  post("/api/fs/load-prg?" + fsQuery(vol, path));

// Replace an editable config file with `text`.
export const saveFile = (vol, path, text) =>
  post("/api/fs/save?" + fsQuery(vol, path), {
    headers: WEB_HEADER,
    body: text,
  });

// Create the folder `path` (its parent must exist).
export const makeDir = (vol, path) =>
  post("/api/fs/mkdir?" + fsQuery(vol, path), { headers: WEB_HEADER });

// Rename the file or folder at `path` to `newName`, in the same folder.
export const renameEntry = (vol, path, newName) =>
  post("/api/fs/rename?" + fsQuery(vol, path) +
       "&to=" + encodeURIComponent(newName), { headers: WEB_HEADER });

export const transferEntry = (vol, path, destVol, destPath, move = false) =>
  post("/api/fs/transfer?" + fsQuery(vol, path) +
       "&dest_vol=" + encodeURIComponent(destVol) +
       "&dest_path=" + encodeURIComponent(destPath) +
       "&move=" + (move ? "1" : "0"), { headers: WEB_HEADER });

// The file's original modified time as local "YYYY-MM-DDTHH:MM:SS" (FAT
// stores no time zone, and the file list shows the stored value as-is).
function localMtime(file) {
  if (!file.lastModified) return "";
  const d = new Date(file.lastModified);
  const p = (n) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
    "T" + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
}

// Upload `file` to `path`. XHR rather than fetch so we get progress events.
// A rejected promise carries `.conflict = true` when the file already exists.
export function upload(vol, path, file, { overwrite = false, onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const mtime = localMtime(file);
    xhr.open("POST", "/api/fs/upload?" + fsQuery(vol, path) +
      (mtime ? "&mtime=" + encodeURIComponent(mtime) : "") +
      (overwrite ? "&overwrite=1" : ""));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) { resolve(); return; }
      const bodyText = (xhr.responseText || "").trim();
      const err = new ApiError(xhr.status, bodyText);
      if (xhr.status === 409 && /exist/i.test(bodyText)) err.conflict = true;
      reject(err);
    };
    xhr.onerror = () => reject(new Error("network error"));
    xhr.send(file);
  });
}

// Protection is independent of logical deletion. Off requires explicit consent.
export const getConfigProtection = () => getJson("/api/configs/protection");
export const setConfigProtection = (id, on, confirmed = false) =>
  post("/api/configs/protection?id=" + encodeURIComponent(id) + "&on=" + (on ? 1 : 0) +
       "&confirmed=" + (confirmed ? 1 : 0), { headers: WEB_HEADER });

export const downloadFolderUrl = (vol, path) => "/api/fs/download-folder?" + fsQuery(vol, path);

export const saveFan = (enabled, on, off) => post(
  `/api/fan?enabled=${encodeURIComponent(enabled)}&on=${encodeURIComponent(on)}&off=${encodeURIComponent(off)}`,
  { headers: WEB_HEADER });

export const getDatasette = () => getJson("/api/datasette");
export const controlDatasette = (action) => post("/api/datasette/control?action=" + encodeURIComponent(action), { headers: WEB_HEADER });

// Wait for emulator completion; HTTP acceptance alone does not mean attached.
export async function loadTape(vol, path) {
  const reply = await check(await fetch("/api/fs/load-tape?" + fsQuery(vol, path),
    { method: "POST", headers: WEB_HEADER }));
  const { request_id: id } = await reply.json();
  if (!Number.isInteger(id) || id <= 0) throw new Error("Invalid tape request ID");
  for (let i = 0; i < 100; i++) {
    const state = await getDatasette();
    if (state.serial !== id) throw new Error("Tape request superseded; check Datasette");
    if (!state.pending) {
      if (state.error || !state.attached) throw new Error("Tape attachment failed (" + state.error + ")");
      globalThis.document?.dispatchEvent?.(new Event("datasette-attached"));
      return state;
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error("Tape attachment timed out; check Datasette before retrying");
}
