import { confirmE64 } from "./dialog.js";
// Dashboard view and the Pi/system controls: status polling, hardware and
// storage meters, and the reboot / shut down / hard reset / disable-web-UI
// actions.

import { updateHotkeys } from "./instructions.js";
import { $, fmtUptime, fmtKB } from "./util.js";
import * as api from "./api.js";
import { setMachine } from "./machine.js";

// ---- status polling (polite: back off on failure, pause when hidden) ----

const POLL_OK_MS = 5000;
const POLL_FAIL_MS = 12000;
let pollTimer = null;
const DRIVE_POLL_MS = 250;
const DRIVE_TIMEOUT_MS = 2000;
const driveUnits = [8, 9, 10, 11];
const dualDriveTypes = [2040, 3040, 4040, 8050, 8250];
const driveActivity = new Array(4);
let driveTypes = [];
let driveTimer = null;
let driveRequest = null;
let driveConnected = false;
let statusInFlight = false;
const driveLedTimers = new Array(4);
let rebooting = false;
// Set once a shut down has been sent; the page then stays offline.
let shutDown = false;
let webUiStopped = false;

function setConn(ok, text) {
  $("sys-dot").className = "dot " + (ok ? "ok" : "bad");
  $("sys-state").textContent = text || (ok ? "System Online" : "Offline");
}

function renderTemp(t, fanOutput) {
  const wrap = $("d-tempmeter");
  if (t == null || isNaN(Number(t))) {
    wrap.hidden = typeof fanOutput !== "boolean";
    $("d-temp").textContent = "Unavailable";
    $("d-temp-bar").style.width = "0%";
    return;
  }
  t = Number(t);
  const cls = t >= 70 ? "v-bad" : t >= 65 ? "v-orange" : t > 60 ? "v-warn" : "v-ok";
  const val = $("d-temp");
  val.textContent = t.toFixed(1) + " °C";
  val.className = cls;
  const bar = $("d-temp-bar");
  bar.style.width = (t<30?0:Math.min(100,Math.log1p(.4*t-12)*32.85))  + "%";
  bar.style.background =
    t >= 70 ? "var(--red)" : t >= 65 ? "var(--orange)" : t > 60 ? "var(--yellow)" : "var(--green)";
  wrap.hidden = false;
}

// Raspberry Pi get_throttled bits. Bits 0-3 are the current state; bits
// 16-19 latch "has happened since boot" and only clear on reboot, so
// each is shown on its own row rather than mixed into the live value.
const BIT_UNDERVOLT_NOW = 1 << 0;
const BIT_FREQ_CAP_NOW = 1 << 1;
const BIT_THROTTLED_NOW = 1 << 2;
const BIT_SOFT_TEMP_NOW = 1 << 3;
const BIT_UNDERVOLT_EVER = 1 << 16;
const BIT_FREQ_CAP_EVER = 1 << 17;
const BIT_THROTTLED_EVER = 1 << 18;
const BIT_SOFT_TEMP_EVER = 1 << 19;

// el gets "Yes (<detail>)" / "No"; bad rows use `cls`, "No" is always ok.
function yesNo(id, bad, cls, hex, detail) {
  const el = $(id);
  el.textContent = bad ? ("Yes" + (detail ? " — " + detail : "")) : "No";
  el.className = bad ? "v-bad" : "v-ok";
  el.title = "get_throttled: 0x" + hex;
}

function renderThermalFlags(raw) {
  const ids = ["d-uv", "d-uv-boot", "d-thr", "d-thr-boot"];
  if (raw == null) {
    ids.forEach((id) => { const e = $(id); e.textContent = "—"; e.className = ""; e.title = ""; });
    return;
  }
  const b = Number(raw) >>> 0;
  const hex = b.toString(16);

  yesNo("d-uv", b & BIT_UNDERVOLT_NOW, "v-bad", hex);
  yesNo("d-uv-boot", b & BIT_UNDERVOLT_EVER, "v-warn", hex);

  let detail = "";
  if (!(b & BIT_THROTTLED_NOW) && (b & BIT_FREQ_CAP_NOW)) detail = "turbo capped";
  else if (!(b & BIT_THROTTLED_NOW) && (b & BIT_SOFT_TEMP_NOW)) detail = "1.2 GHz, warm";
  yesNo("d-thr", b & (BIT_THROTTLED_NOW | BIT_FREQ_CAP_NOW | BIT_SOFT_TEMP_NOW),
        (b & BIT_THROTTLED_NOW) ? "v-bad" : "v-warn", hex, detail);

  yesNo("d-thr-boot",
        b & (BIT_THROTTLED_EVER | BIT_FREQ_CAP_EVER | BIT_SOFT_TEMP_EVER),
        "v-warn", hex);
}

function scheduleStatus(ms) {
  clearTimeout(pollTimer);
  pollTimer = null;
  if (document.hidden) return;
  pollTimer = setTimeout(pollStatus, ms);
}

function renderDriveLed(unit, index, state, primaryKind) {
  const led = $("drive-led-" + unit);
  const previous = driveActivity[index];
  driveActivity[index] = state;
  // VICE places the second IEEE-488 mechanism in the next status slot.
  const secondMechanism = (index & 1) && (state & 1) &&
    dualDriveTypes.includes(primaryKind);
  const label = secondMechanism ? "Drive " + (unit - 1) + " mechanism 1" : "Drive " + unit;
  const enabled = (state & 1) !== 0;
  const active = enabled && (state & 2) !== 0;
  const pulse = enabled && !active && previous != null &&
    (state >>> 2) !== (previous >>> 2);
  const show = (on) => {
    const description = label + " activity: " + (on ? "active" : "inactive");
    if (led.title === description) return;
    led.classList.toggle("active", on);
    led.setAttribute("aria-label", description);
    led.title = description;
  };
  if (!enabled || active || pulse) {
    clearTimeout(driveLedTimers[index]);
    driveLedTimers[index] = null;
  }
  if (pulse) {
    driveLedTimers[index] = setTimeout(() => {
      driveLedTimers[index] = null;
      renderDriveLed(unit, index, driveActivity[index], driveTypes[index - 1]);
    }, 350);
  }
  show(active || driveLedTimers[index] != null);
}

function canPollDriveActivity() {
  return driveConnected && navigator.onLine && !document.hidden &&
    !$("view-dashboard").hidden && !rebooting && !shutDown && !webUiStopped;
}

export function syncDriveActivity() {
  if (!canPollDriveActivity()) {
    clearTimeout(driveTimer);
    driveTimer = null;
    driveRequest?.abort();
    if (driveActivity.some(state => state != null)) {
      driveUnits.forEach((unit, index) => renderDriveLed(unit, index, 0));
      driveActivity.fill(undefined);
    }
    return;
  }
  if (driveTimer === null && driveRequest === null) {
    driveTimer = setTimeout(pollDriveActivity, DRIVE_POLL_MS);
  }
}

function setDriveConnection(connected) {
  driveConnected = connected;
  syncDriveActivity();
}

async function pollDriveActivity() {
  driveTimer = null;
  if (!canPollDriveActivity() || driveRequest) return;
  const request = new AbortController();
  driveRequest = request;
  const timeout = setTimeout(() => {
    if (!request.signal.aborted) setDriveConnection(false);
  }, DRIVE_TIMEOUT_MS);
  try {
    const states = await api.getDriveActivity(request.signal);
    if (request.signal.aborted || !canPollDriveActivity()) return;
    if (!Array.isArray(states) || states.length !== driveUnits.length ||
        !states.every(state => Number.isInteger(state) && state >= 0 && state <= 0xffffffff)) {
      throw new Error("Invalid drive activity response");
    }
    driveUnits.forEach((unit, index) => {
      renderDriveLed(unit, index, states[index], driveTypes[index - 1]);
    });
  } catch {
    if (!request.signal.aborted) setDriveConnection(false);
  } finally {
    clearTimeout(timeout);
    driveRequest = null;
    syncDriveActivity();
  }
}

async function pollStatus() {
  if (statusInFlight || shutDown || webUiStopped) return;
  statusInFlight = true;
  let ok = false;
  try {
    const s = await api.getStatus();

    $("sc-uptime").textContent = fmtUptime(s.uptime_secs);
    $("sc-ip").textContent = s.ip || "—";

    renderTemp(s.soc_temp_c, s.fan_on);
    $("d-modem-address").textContent = (s.virtual_modem_address || "—").replace(/^\$/, "");
    $("d-ftdi").textContent = s.ftdi_rs232 || "—";
    $("d-audio").textContent = s.audio_output || "—";
    renderJoystickSwap(s);
    renderThermalFlags(s.throttled);

    $("sc-host").textContent = s.hostname || "—";
    setMachine(s);
    updateHotkeys(s.hotkeys, s.config_id);
    const fan = $("d-fan");
    fan.hidden = typeof s.fan_on !== "boolean";
    fan.style.color = s.fan_on ? "var(--green)" : "var(--c64-medium-gray)";
    fan.title = s.fan_on ? "Fan output ON (no rotation feedback)" : "Fan output OFF (no rotation feedback)";
    $("sc-net").textContent =
      (s.net_text || "").toLowerCase().startsWith("connected")
        ? "Connected"
        : (s.net_text || ("status " + s.net_status));
    const pill = $("i-warp").firstElementChild;
    pill.textContent = s.warp === 1 ? "Enabled" : s.warp === 0 ? "Disabled" : "—";
    pill.className = "warp-pill" + (s.warp === 1 ? " on" : "");
    $("qa-warp-sub").textContent =
      s.warp === 1 ? "Enabled" :
      s.warp === 0 ? "Disabled" : "Unavailable";
    const reuPill = $("i-reu").firstElementChild;
    reuPill.textContent = s.reu === 1 ? "Enabled" :
      s.reu === 0 ? "Disabled" : "—";
    reuPill.className = "warp-pill" + (s.reu === 1 ? " on" : "");

    $("i-reu-size").textContent =
      s.reu === 1 && s.reu_size > 0
        ? (s.reu_size >= 1024
            ? (s.reu_size / 1024) + " MB"
            : s.reu_size + " KB")
        : s.reu === 0 ? "None" : "—";

    const ieeePill = $("i-ieee488").firstElementChild;
    ieeePill.textContent = s.ieee488 === 1 ? "Enabled" :
      s.ieee488 === 0 ? "Disabled" : "—";
    ieeePill.className = "warp-pill" + (s.ieee488 === 1 ? " on" : "");
    const driveNames = {
      0: "None", 1540: "1540", 1541: "1541", 1542: "1541-II",
      1551: "1551", 1570: "1570", 1571: "1571", 1573: "1571CR",
      2031: "2031", 2040: "2040", 3040: "3040", 4040: "4040",
      8050: "8050", 8250: "8250", 1001: "SFD-1001",
      1581: "1581", 2000: "CMD FD-2000", 4000: "CMD FD-4000", 4844: "CMD HD",
    };
    driveTypes = Array.isArray(s.drives) ? s.drives : [];
    driveUnits.forEach((unit, index) => {
      const kind = driveTypes[index];
      $("i-drive" + unit).textContent = Number.isInteger(kind)
        ? (driveNames[kind] || "Type " + kind) : "—";
    });

    if (rebooting) {
      rebooting = false;
      $("action-msg").className = "msg";
      $("action-msg").textContent = "E64 is back online.";
      $("nav-reboot").disabled = false;
    }
    ok = true;
  } catch (e) {
    if (e.status === 401) {
      setDriveConnection(false);
      setConn(false, "Locked");
      $("action-msg").className = "msg err";
      $("action-msg").textContent =
        "Authentication required. Reload the page and enter the Web UI PIN.";
      clearTimeout(pollTimer);
      pollTimer = null;
      return;
    }
    /* otherwise keep last known values */
  } finally {
    statusInFlight = false;
  }
  setDriveConnection(ok && navigator.onLine);
  setConn(ok);
  scheduleStatus(ok ? POLL_OK_MS : POLL_FAIL_MS);
}

export function startStatusPolling() {
  pollStatus();
}

export async function refreshVolumes() {
  const display = (v, prefix) => {
    const meter = $(prefix);
    const fallback = {"d-storage":"SD Card", "d-usb-storage":"USB 1", "d-usb2-storage":"USB 2", "d-usb3-storage":"USB 3"}[prefix];
    $(prefix + "-label").textContent = fallback + (v && v.label ? ": " + v.label : "");
    if (!v || !v.total_kb) { meter.hidden = true; return; }
    const usedKb = Math.max(0, v.total_kb - v.free_kb);
    const pct = Math.min(100, Math.round((usedKb / v.total_kb) * 100));
    $(prefix + "-bar").style.width = pct + "%";
    $(prefix + "-txt").textContent =
      fmtKB(v.free_kb) + " free of " + fmtKB(v.total_kb);
    meter.hidden = false;
  };
  try {
    const v = (await api.getVolumes(true)).volumes || [];
    display(v.find((x) => x.id === "SD"), "d-storage");
    display(v.find((x) => x.id === "USB"), "d-usb-storage");
    display(v.find((x) => x.id === "USB2"), "d-usb2-storage");
    display(v.find((x) => x.id === "USB3"), "d-usb3-storage");
  } catch (e) {
    display(null, "d-storage");
    display(null, "d-usb-storage");
    display(null, "d-usb2-storage");
    display(null, "d-usb3-storage");
  }
}

// ---- power / web UI actions ----

// Send the reboot command without asking; the caller has already confirmed.
export async function rebootNow() {
  rebooting = true;
  setDriveConnection(false);
  $("nav-reboot").disabled = true;
  $("action-msg").className = "msg";
  $("action-msg").textContent = "Sending reboot command…";
  try {
    await api.reboot();
  } catch (e) {
    /* the connection usually drops as it reboots; that is expected */
  }
  $("action-msg").textContent = "E64 is rebooting. This page will reconnect automatically.";
  scheduleStatus(POLL_FAIL_MS);
}

async function doReboot() {
  if (!await confirmE64("Reboot E64?\nUnsaved changes will be lost.", "Reboot")) return;
  await rebootNow();
}

async function doShutdown() {
  if (!await confirmE64(
    "Shut Down E64?\nUnsaved changes will be lost.\nPower cycle to restart.", "Shut Down")) return;
  for (const id of ["nav-shutdown", "nav-reboot"]) {
    $(id).disabled = true;
  }
  $("action-msg").className = "msg";
  $("action-msg").textContent = "Sending shut down command…";
  try {
    await api.shutdown();
  } catch (e) {
    if (e.status) {
      $("action-msg").className = "msg err";
      $("action-msg").textContent = "Could not shut down — " + e.message;
      for (const id of ["nav-shutdown", "nav-reboot"]) {
        $(id).disabled = false;
      }
      return;
    }
    /* no answer: the connection dropped as it went down */
  }
  shutDown = true;
  setDriveConnection(false);
  clearTimeout(pollTimer);
  pollTimer = null;
  setConn(false, "Off");
  $("action-msg").textContent =
    "E64 is shutting down. Once its screen goes blank it is safe to " +
    "remove power. Reload this page after switching it on again.";
}

// Show a successful Quick Action message for three seconds.
let actionMessageTimer = null;

function showTemporaryActionMessage(message) {
  clearTimeout(actionMessageTimer);

  const element = $("action-msg");
  element.className = "msg";
  element.textContent = message;

  actionMessageTimer = setTimeout(() => {
    if (element.textContent === message) {
      element.textContent = "";
    }
    actionMessageTimer = null;
  }, 3000);
}

async function doHardReset() {
  if (!await confirmE64(
    "Hard reset the emulated machine now?\n\n")) return;
  $("qa-reset").disabled = true;
  $("action-msg").className = "msg";
  $("action-msg").textContent = "Sending hard reset…";
  try {
    await api.hardReset();
    showTemporaryActionMessage("Machine reset.");
  } catch (e) {
    $("action-msg").className = "msg err";
    $("action-msg").textContent = "Hard reset failed — " + e.message;
  }
  $("qa-reset").disabled = false;
}

async function disableWebUi() {
  if (!await confirmE64(
    "Disable the Web UI now?\n\n" +
    "The server stops immediately. It starts again after the next reboot " +
    "unless you also turn it off in the Network menu.")) return;
  $("qa-disable").disabled = true;
  $("action-msg").className = "msg";
  $("action-msg").textContent = "Stopping the Web UI…";
  try {
    await api.disableWebUi();
  } catch (e) {
    $("action-msg").className = "msg err";
    $("action-msg").textContent = "Could not stop the Web UI — " + e.message;
    $("qa-disable").disabled = false;
    return;
  }
  webUiStopped = true;
  setDriveConnection(false);
  clearTimeout(pollTimer);
  pollTimer = null;
  setConn(false, "Stopped");
  $("action-msg").textContent =
    "Web UI stopped. This page is now offline; it returns after the next " +
    "reboot unless disabled in the Network menu.";
}

async function doSoftReset() {
  if (!await confirmE64("Soft reset the C64 now?")) return;
  const button = $("qa-soft-reset");
  button.disabled = true;
  $("action-msg").className = "msg";
  $("action-msg").textContent = "Sending soft reset...";
  try {
    await api.softReset();
    showTemporaryActionMessage("Soft reset requested.");
  } catch (e) {
    $("action-msg").className = "msg err";
    $("action-msg").textContent = "Soft reset failed — " + e.message;
  } finally {
    button.disabled = false;
  }
}

async function doWarpToggle() {
  const button = $("qa-warp");
  button.disabled = true;
  $("action-msg").className = "msg";
  $("action-msg").textContent = "Toggling Warp Mode...";
  try {
    await api.toggleWarp();
    showTemporaryActionMessage("Warp toggle requested.");
    await pollStatus();
  } catch (e) {
    $("action-msg").className = "msg err";
    $("action-msg").textContent = "Warp toggle failed — " + e.message;
  } finally {
    button.disabled = false;
  }
}

function renderJoystickSwap(s) {
  const available = s.joystick_swap === 0 || s.joystick_swap === 1;
  $("qa-swap-sub").textContent = s.joystick_swap === 1 ? "Reversed" :
    s.joystick_swap === 0 ? "Normal" : "Unavailable";
  $("qa-swap").disabled = !available || joystickSwapBusy;
  $("qa-swap").setAttribute("aria-pressed", String(s.joystick_swap === 1));
}
let joystickSwapBusy = false;
async function doJoystickSwap() {
  if (joystickSwapBusy) return;
  joystickSwapBusy = true;
  $("qa-swap").disabled = true;
  try {
    await api.swapJoysticks();
    showTemporaryActionMessage("Joystick swap requested.");
    await pollStatus();
  } catch (e) {
    $("action-msg").className = "msg err";
    $("action-msg").textContent = "Joystick swap failed — " + e.message;
  } finally {
    joystickSwapBusy = false;
    $("qa-swap").disabled = false;
    // Requests execute on the emulator loop; fetch the resulting live state.
    scheduleStatus(250);
  }
}

export function initDashboard() {
  $("nav-reboot").addEventListener("click", doReboot);
  $("nav-shutdown").addEventListener("click", doShutdown);
  $("qa-soft-reset").addEventListener("click", doSoftReset);
  $("qa-reset").addEventListener("click", doHardReset);
  $("qa-warp").addEventListener("click", doWarpToggle);
  $("qa-swap").addEventListener("click", doJoystickSwap);

  $("qa-disable").addEventListener("click", disableWebUi);
  document.addEventListener("visibilitychange", () => {
    syncDriveActivity();
    if (document.hidden) { clearTimeout(pollTimer); pollTimer = null; }
    else if (!shutDown && !webUiStopped) pollStatus();
  });
  window.addEventListener("offline", () => setDriveConnection(false));
  window.addEventListener("online", () => {
    if (!document.hidden) pollStatus();
  });
}
