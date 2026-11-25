import { getDatasette, controlDatasette } from "./api.js";

let visible = false, timer = null, running = false, submitting = false, state = null, stopRequested = false, revision = 0, activeAction = null;
// Exact palette from third_party/vice-3.3/data/C64/godot.vpl, in C64 index order.
const cassetteColors = ["#000000", "#FFFFFF", "#880000", "#AAFFEE", "#CC44CC", "#00CC55", "#0000AA", "#EEEE77", "#DD8855", "#664400", "#FE7777", "#333333", "#777777", "#AAFF66", "#0088FF", "#BBBBBB"];
let cassetteIdentity = null, cassetteColor = null;
const el = id => document.getElementById(id);
const buttons = () => [...document.querySelectorAll("[data-tape-action]")];
const modes = ["Stopped", "Playing", "Recording", "Rewinding", "Fast Forward"];
// Native animations retain their phase across polls and speed/direction changes.
// The SVG use instances have explicit origins in their existing local viewBox.
let reelAnimations = null, reelRate = 0;
function setReelRate(rate) {
  if (rate === reelRate) return;
  if (!reelAnimations && rate) {
    reelAnimations = [...el("tape-reels").querySelectorAll("use")].map(reel => {
      reel.style.transformBox = "view-box";
      reel.style.transformOrigin = reel.getAttribute("x") + "px " + reel.getAttribute("y") + "px";
      const animation = reel.animate([{ transform: "rotate(0deg)" }, { transform: "rotate(-360deg)" }],
        { duration: 2400, iterations: Infinity, easing: "linear" });
      animation.pause();
      animation.currentTime = 0;
      return animation;
    });
  }
  reelRate = rate;
  reelAnimations?.forEach(animation => {
    if (!rate) animation.pause();
    else {
      // Reverse playback must have time before zero; whole turns preserve the angle.
      if (rate < 0 && animation.currentTime < 2400) animation.currentTime += 2400 * 1000000;
      animation.updatePlaybackRate(rate);
      animation.play();
    }
  });
}
function renderReelMotion(s) {
  const moving = visible && !document.hidden && s.supported && s.attached && (s.motor === 1 || s.motor === true);
  // Counterclockwise forward viewed through the cassette door; rewind reverses both.
  setReelRate(moving ? ({1: 1, 2: 1, 3: -4, 4: 4}[s.mode] || 0) : 0);
}
function renderCounter(value) {
  const counter = el("tape-counter");
  if (counter.children?.length === 3) {
    [...counter.children].forEach((digit, i) => { digit.textContent = value[i] || ""; });
  } else counter.textContent = value;
}
export function renderDatasette(s) {
  // Decoration follows attachment transitions, never transport serials (those change on commands).
  const identity = s.attached ? String(s.filename) : null;
  if (identity !== null && identity !== cassetteIdentity) {
    cassetteColor = cassetteColors[Math.floor(Math.random() * cassetteColors.length)];
  }
  cassetteIdentity = identity;
  if (identity !== null) el("tape-cassette").setAttribute("fill", cassetteColor);
  state = s;
  renderReelMotion(s);
  if (!s.pending && !submitting) activeAction = null;
  const loaded = !!s.attached;
  el("tape-cassette").toggleAttribute("hidden", !loaded);
  el("tape-label").hidden = !loaded;
  el("tape-winding").toggleAttribute("hidden", !loaded);
  el("tape-reels").toggleAttribute("hidden", !loaded);
  el("tape-motor").setAttribute("data-on", String(!!s.supported && !!s.motor));
  el("tape-motor").setAttribute("aria-label", s.supported ? (s.motor ? "Tape motor on" : "Tape motor off") : "Motor state unavailable");
  buttons().forEach(b => b.setAttribute("data-recording", String(!!s.supported && loaded && s.mode === 2 && !!s.motor)));
  buttons().forEach(b => b.setAttribute("aria-pressed", String(!!s.supported && loaded && ((b.dataset.tapeAction === "play" && (s.mode === 1 || s.mode === 2)) || (b.dataset.tapeAction === "record" && s.mode === 2) || (b.dataset.tapeAction === "rewind" && s.mode === 3) || (b.dataset.tapeAction === "forward" && s.mode === 4)))));
  const filename = loaded ? String(s.filename).split(/[\\/]/).pop().replace(/\.tap$/i, "") : "";
  el("tape-label").textContent = filename;
  el("tape-label").setAttribute("style", "font-size:min(" + Math.max(10, Math.min(19, 520 / Math.max(1, filename.length))) + "px, calc(3.3cqw - 1.5px))");
  el("tape-label").title = loaded ? s.filename : "";
  el("tape-drawing").setAttribute("aria-label", loaded ? "Datasette cassette: " + filename : "Empty Datasette compartment");
  renderCounter(loaded ? String(((s.counter % 1000) + 1000) % 1000).padStart(3, "0") : "000");
  el("tape-status").textContent = !s.supported ? "Datasette unavailable" : !loaded ? "No Tape Loaded" : (modes[s.mode] || "Unknown transport state");
  const errors = {1: "Tape changed or Datasette unavailable. Try again.", 2: "Transport unavailable during event playback or network play.", 3: "Tape is read only.", 4: "Could not eject tape.", 5: "Could not attach tape. Check the file and drive."};
  el("tape-error").textContent = errors[s.error] || (s.error ? "Datasette command failed." : "");
  buttons().forEach(b => { b.disabled = !s.supported || !loaded || (b.dataset.tapeAction === "record" && !s.writable); });
}
function fail(error) {
  setReelRate(0);
  buttons().forEach(b => { b.disabled = true; });
  el("tape-status").textContent = "Tape state unavailable";
  renderCounter("—");
  el("tape-motor").setAttribute("data-on", "false");
  el("tape-motor").setAttribute("aria-label", "Motor state unavailable");
  buttons().forEach(b => { b.setAttribute("aria-pressed", "false"); b.setAttribute("data-recording", "false"); });
  el("tape-error").textContent = error.message;
}
async function poll() {
  clearTimeout(timer);
  if (!visible || document.hidden || running) return;
  running = true;
  let delay = 1000;
  const snapshot = revision;
  try {
    const next = await getDatasette();
    if (snapshot === revision && visible && !document.hidden) {
      renderDatasette(next);
      if (stopRequested && !submitting && !next.pending) {
        stopRequested = false;
        const stop = buttons().find(b => b.dataset.tapeAction === "stop");
        if (stop && !stop.disabled) void sendCommand("stop");
      }
      if (next.pending) delay = 100;
    }
  }
  catch (e) { if (snapshot === revision) fail(e); delay = 5000; }
  finally { running = false; if (visible && !document.hidden) timer = setTimeout(poll, snapshot === revision ? delay : 0); }
}
export function setDatasetteVisible(value) {
  visible = value; clearTimeout(timer);
  setReelRate(0);
  if (value) poll();
}
export function initDatasette() {
  document.addEventListener("datasette-attached", () => { cassetteIdentity = null; setReelRate(0); });
  el("tape-help-toggle").addEventListener("click", () => {
    const open = el("tape-help-toggle").getAttribute("aria-expanded") !== "true";
    el("tape-help-toggle").setAttribute("aria-expanded", String(open));
    el("tape-help").hidden = !open;
  });
  buttons().forEach(b => b.addEventListener("click", () => {
    if (b.disabled) return;
    const action = b.dataset.tapeAction;
    if (submitting || state?.pending) {
      if (action === "stop" && activeAction !== "stop") stopRequested = true;
      return;
    }
    return sendCommand(action);
  }));
  document.addEventListener("visibilitychange", () => { clearTimeout(timer); setReelRate(0); if (!document.hidden) poll(); });
}

async function sendCommand(action) {
  submitting = true;
  activeAction = action;
  revision++;
  clearTimeout(timer);
  try {
    await controlDatasette(action);
    // Acceptance is not completion. Hold the request guard until sampled again.
    if (state) state = { ...state, pending: 1 };
  } catch (e) { stopRequested = false; fail(e); }
  finally {
    submitting = false;
    // Refresh immediately; an older in-flight poll will schedule a fresh read.
    if (visible) void poll();
  }
}
