import { confirmE64, promptE64 } from "./dialog.js";
// The Configs page: the configs on the SD card (docs/CONFIGS.md), which
// one is running, which starts next and their settings. It only
// reads /configs; each config's files open in the usual editor.

import { $ } from "./util.js";
import * as api from "./api.js";
import { openEditor } from "./editor.js";
import { filesHash, selectFilesVolume } from "./files.js";
import { toggleMenu } from "./menu.js";
import { setMachine } from "./machine.js";
import {
  FIRST_DRIVE, DEFAULT_ID, MAX_CONFIG_NAME, baseName, cleanName,
  settingsFile,
  groupConfigs, idValid, configVideoStandard, machineLabel, parseActive,
  parseConfig, withName,
} from "./configs_data.js";
import { FACTORY_CONFIGS, isFactory } from "./configs_data.js";

let pfVol = "SD";
let loading = false;
let restoring = false;
// What the page last showed: running, power-on and Start-once ids, and the
// machine running now ("C64").
let lastState = { running: "", powerOn: DEFAULT_ID, once: "", machine: "" };

function setMsg(text, isErr) {
  $("pf-status").className = "msg" + (isErr ? " err" : "");
  $("pf-status").textContent = text;
}

// A file's text, or null if it can't be read (missing, for example).
async function readText(path) {
  try {
    return new TextDecoder("utf-8").decode(await api.readFile(pfVol, path));
  } catch (e) {
    if (e.status === 401) throw e;
    return null;
  }
}

async function editFile(path) {
  const result = await openEditor({ vol: pfVol, path, name: baseName(path) });
  if (result.saved && !result.rebooting) loadConfigs();
}

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function badge(text, kind) {
  return el("span", "pf-badge " + kind, text);
}

// What the config does at power-on: its autostart and startup disks.
function startsList(p) {
  const ul = el("ul", "pf-starts");
  const add = (key, path) => {
    const li = el("li");
    li.appendChild(el("span", "k", key));
    const v = el("span", "v", baseName(path));
    v.title = path;
    li.appendChild(v);
    ul.appendChild(li);
  };
  if (p.autostart) add("Autostart", p.autostart);
  p.disks.forEach((disk, i) => { if (disk) add("Drive " + (FIRST_DRIVE + i), disk); });
  if (!ul.childElementCount) {
    const li = el("li", "none", "No autostart or disks");
    ul.appendChild(li);
  }
  return ul;
}

function configCard(p, state, actions) {
  const card = el("article", "pf-card");
  if (p.id === state.running) card.classList.add("running");

  const top = el("div", "pf-top");
  const name = el("div", "pf-name" + (isFactory(p.id) ? " pf-factory-name" : ""));
  name.appendChild(el("span", "pf-active-marker", p.id === state.running ? "*" : ""));
  name.appendChild(el("span", "pf-name-text", p.name));
  top.appendChild(name);
  card.appendChild(top);

  const badges = el("div", "pf-badges");
  const running = el("div", "pf-running-row");
  if (p.id === state.running) running.appendChild(badge("Running", "run"));
  if (isFactory(p.id) || !state.protectionReady || state.protectedIds.has(p.id)) badges.appendChild(badge("Protected: On", "power"));
  if (p.id === state.once) badges.appendChild(badge("Next start", "once"));
  if (p.description) card.appendChild(el("div", "pf-desc", p.description));
  card.appendChild(startsList(p));
  card.appendChild(startButtons(p));

  card.appendChild(running);
  const bar = el("div", "pf-actions pf-card-footer");
  const standard = configVideoStandard(p.machine);
  if (standard) bar.appendChild(badge(standard, "video-standard " + standard.toLowerCase()));
  if (badges.children.length) bar.appendChild(badges);
  for (const action of actions.buttons) {
    const b = el("button", "btn", action.label);
    b.type = "button";
    b.title = action.title || action.label;
    b.addEventListener("click", action.run);
    bar.appendChild(b);
  }
  if (actions.menu.length) {
    const b = el("button", "btn act-btn pf-more", "Actions ▾");
    b.type = "button";
    b.title = "Actions for " + p.name;
    b.setAttribute("aria-haspopup", "menu");
    b.setAttribute("aria-expanded", "false");
    b.addEventListener("click", () => toggleMenu(b, actions.menu));
    bar.appendChild(b);
  }
  card.appendChild(bar);
  return card;
}

// The config's settings for its machine; an older config has them in
// settings.txt until it next starts.
async function editSettings(dir, machine) {
  const own = dir + "/" + settingsFile(machine);
  const legacy = dir + "/settings.txt";
  const path = (await readText(own)) === null && (await readText(legacy)) !== null
    ? legacy : own;
  editFile(path);
}

// ---- Switch to / Start once ----

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// The config's choice ("start" in config.txt) is the main button.
function startButtons(p) {
  const row = el("div", "pf-start");
  const make = (once) => {
    const b = el("button", "btn", once ? "Start Once" : "▶ Switch To");
    b.type = "button";
    b.title = once ? "Restart into " + p.name + " for this session only"
                   : "Restart into " + p.name + " and use it at every power-on";
    b.addEventListener("click", () => startConfig(p, once));
    return b;
  };
  const first = p.start === "once";
  const main = make(first);
  main.classList.add("btn-primary");
  row.appendChild(main);
  row.appendChild(make(!first));
  return row;
}

function showRestart(title, text, { spinning = true, closable = false } = {}) {
  $("pf-restart-title").textContent = title;
  $("pf-restart-msg").textContent = text;
  $("pf-restart-spin").hidden = !spinning;
  $("pf-restart-close").hidden = !closable;
  $("pf-restart").hidden = false;
  document.body.classList.add("modal-open");
  if (closable) $("pf-restart-close").focus();
}

function hideRestart() {
  $("pf-restart").hidden = true;
  document.body.classList.remove("modal-open");
}

async function startConfig(p, once) {
  const target = (p.machine.split("/")[0] || "").trim().toLowerCase();
  const label = machineLabel(p.machine);
  const current = lastState.machine.toLowerCase();
  const otherMachine = target && current && target !== current;
  let question = once
    ? "Start “" + p.name + "” once?\nYour usual Config starts at next power-on."
    : "Switch To “" + p.name + "”?\nUse this Config at power-on.";
  if (otherMachine) question += "\nSwitch machine to " + label + ".";
  if (!await confirmE64(question + "\nUnsaved changes will be lost.", once ? "Start Once" : "Switch To")) return;

  let uptime = Infinity;
  try {
    uptime = (await api.getStatus()).uptime_secs;
  } catch (e) {
    /* checked again below */
  }
  try {
    await api.startConfig(p.id, once);
  } catch (e) {
    setMsg("Could not start " + p.name + " — " + e.message, true);
    return;
  }
  await waitForRestart(p.name, uptime);
}

// Waits for E64 to restart (it goes offline, or its uptime starts again),
// or for the reason it couldn't.
async function waitForRestart(name, uptimeBefore) {
  showRestart("Restarting into " + name + "…",
              "E64 is restarting. This page reconnects by itself.");
  let wentDown = false;
  const giveUp = Date.now() + 120000;
  while (Date.now() < giveUp) {
    await sleep(1500);
    let s = null;
    try {
      s = await api.getStatus();
    } catch (e) {
      if (e.status === 401) {
        hideRestart();
        setMsg("Authentication required — reload the page and enter the PIN.", true);
        return;
      }
    }
    if (!s) {
      wentDown = true;
      continue;
    }
    const restarted = wentDown || s.uptime_secs < uptimeBefore;
    if (!restarted && s.config_error) {
      hideRestart();
      setMsg("Could not start " + name + " — " + s.config_error, true);
      return;
    }
    if (restarted) {
      hideRestart();
      await loadConfigs();
      return;
    }
  }
  showRestart("Still waiting for E64",
              "It hasn't come back yet. Refresh this page once it has.",
              { spinning: false, closable: true });
}

// ---- rename / delete ----

// Like the menu's Rename: only the name changes, not the folder (id).
async function renameConfig(p) {
  const input = await promptE64("Rename Config", "Rename “" + p.name + "” to:", p.name, "Rename");
  if (input === null) return;
  const name = cleanName(input);
  if (!name) { setMsg(`Use a nonempty Config name of at most ${MAX_CONFIG_NAME} UTF-8 bytes.`, true); return; }
  if (name === p.name) return;
  const path = "/configs/" + p.id + "/config.txt";
  setMsg("Renaming " + p.name + "…");
  try {
    const text = await readText(path);
    if (text === null) throw new Error("can't read config.txt");
    await api.saveFile(pfVol, path, withName(text, name));
  } catch (e) {
    setMsg("Could not rename " + p.name + " — " + e.message, true);
    return;
  }
  await loadConfigs();
  setMsg("Renamed " + p.name + " to " + name + "." +
         (p.id === lastState.running
           ? " The E64 menu shows the new name after a restart." : ""));
}

// Copy to a fresh folder; publish config.txt last so incomplete copies stay hidden.
async function copyConfig(p) {
  const input = await promptE64("Copy Config", "Name for the copy:", cleanName("Copy of " + p.name), "Copy");
  if (input === null) return;
  const name = cleanName(input);
  if (!name) { setMsg(`Use a nonempty Config name of at most ${MAX_CONFIG_NAME} UTF-8 bytes.`, true); return; }
  const src = "/configs/" + p.id;
  const dest = "/configs/copy-" + Date.now().toString(36);
  setMsg("Copying " + p.name + "…");
  try {
    const config = await readText(src + "/config.txt");
    if (config === null) throw new Error("can't read config.txt");
    await api.makeDir(pfVol, dest);
    const copyTree = async (from, to) => {
      const listing = await api.listDir(from, pfVol);
      for (const entry of listing.entries) {
        if (from === src && entry.name.toLowerCase() === "config.txt") continue;
        if (/\.(e64-new|e64-old|e64-ne~|part)$/i.test(entry.name)) continue;
        const source = from + "/" + entry.name, target = to + "/" + entry.name;
        if (entry.dir) { await api.makeDir(pfVol, target); await copyTree(source, target); }
        else await api.transferEntry(pfVol, source, pfVol, target);
      }
    };
    await copyTree(src, dest);
    await api.saveFile(pfVol, dest + "/config.txt", withName(config, name));
    await loadConfigs();
    setMsg("Copied " + p.name + " to " + name + ".");
  } catch (e) { setMsg("Copy failed — " + e.message + ". Any partial copy is retained at " + dest + ".", true); }
}

// No API call or filesystem change occurs until both explicit Yes responses.
async function changeDeleted(p, legacy = false) {
  if (!await confirmE64('Delete Config "' + p.name + '"?', "Yes", "No")) return;
  if (!await confirmE64('Confirm permanent deletion of "' + p.name + '"?', "Yes, Delete", "No")) return;
  try {
    const request = await api.deleteConfigPermanent(p.id, legacy);
    for (let attempt = 0; attempt < 20; attempt++) {
      await sleep(500);
      const state = await api.getDeletedConfigs();
      if (!state.ready) throw new Error("legacy deletion records need recovery");
      const operation = state.operation;
      if (!operation || operation.request_id !== request.request_id || operation.id !== p.id) continue;
      if (operation.state === -1) throw new Error(operation.error || "permanent deletion failed");
      if (operation.state === 2) {
        await loadConfigs();setMsg('Permanently deleted "' + p.name + '".');return;
      }
    }
    throw new Error("request still pending; refresh to check its result");
  } catch (e) { setMsg("Deletion failed — " + e.message, true); }
}
async function deleteConfig(p) { return changeDeleted(p, false); }

async function changeProtection(p, on) {
  if (!on && !await confirmE64("Turn protection Off for “" + p.name + "”?\n\nThis allows deletion.")) return;
  try {
    await api.setConfigProtection(p.id, on, !on);
    for (let i = 0; i < 5; i++) {
      await sleep(1000);
      const state = await api.getConfigProtection();
      if (!state.ready || state.error) throw new Error(state.error || "protection records need recovery");
      if (state.protected.includes(p.id) === on) { await loadConfigs();setMsg("Protection " + (on ? "On" : "Off") + ": " + p.name);return; }
    }
    throw new Error("request pending; refresh to check");
  } catch (e) { setMsg("Protection update failed — " + e.message, true); }
}

// The card's file buttons, and the items of its Actions menu.
function configActions(p) {
  if (isFactory(p.id)) return {buttons:[], menu:[]};
  const dir = "/configs/" + p.id;
  return {
    buttons: [],
    menu: [
      { label: "config.txt", title: "Edit " + dir + "/config.txt",
        run: () => editFile(dir + "/config.txt") },
      { label: "settings", title: "Edit the config's E64 settings for the " +
          (machineLabel(p.machine) || "machine"),
        run: () => editSettings(dir, p.machine) },
      { label: "vice.ini", title: "Edit " + dir + "/vice.ini",
        run: () => editFile(dir + "/vice.ini") },
      { label: "Copy…", run: () => copyConfig(p) },
      { label: "Open Folder", run: () => {
          selectFilesVolume("SD");
          location.hash = filesHash(dir);
        } },
      { label: "Rename…", run: () => renameConfig(p) },
      ...(lastState.protectionReady ? [{ label: "Protected: " + (lastState.protectedIds.has(p.id) ? "On" : "Off"), run: () => changeProtection(p, !lastState.protectedIds.has(p.id)) }] : []),
      // Like the menu, the running config can't be deleted.
      ...(!lastState.protectionReady || lastState.protectedIds.has(p.id) || [lastState.running, lastState.powerOn, lastState.once].includes(p.id) ? [] : [
        { label: "Delete", danger: true, run: () => deleteConfig(p) },
      ]),
    ],
  };
}



function section(title) {
  const frag = document.createDocumentFragment();
  if (title) frag.appendChild(el("h3", "pf-section", title));
  const grid = el("div", "pf-grid");
  frag.appendChild(grid);
  return { frag, grid };
}

export async function loadConfigs() {
  if (loading) return;
  loading = true;
  setMsg("Loading…");
  $("pf-list").textContent = "";
  try {
    await render();
  } catch (e) {
    setMsg("Could not read the configs — " + e.message, true);
  } finally {
    loading = false;
  }
}

async function render() {
  let status = null;
  try {
    status = await api.getStatus();
  } catch (e) {
    if (e.status === 401) throw e;
  }
  if (status) setMachine(status);
  const machine = (status && status.machine) || "";

  let listing = null;
  try {
    listing = await api.listDir("/configs", "SD");
  } catch (e) {
    if (e.status === 401) throw e;
  }
  if (!listing) {
    // Configs and their configuration files always live on the SD card.
    pfVol = "SD";
  } else {
    pfVol = "SD";
  }

  // Configs in folders with a valid id and a valid config.txt, as the
  // menu lists them.
  const configs = FACTORY_CONFIGS.map((p) => ({...p}));
  for (const entry of (listing && listing.entries) || []) {
    if (!entry.dir || !idValid(entry.name)) continue;
    const text = await readText("/configs/" + entry.name + "/config.txt");
    const p = text === null ? null : parseConfig(entry.name, text);
    if (p && !isFactory(p.id)) configs.push(p);
  }

  const activeText = listing ? await readText("/configs/active.txt") : null;
  const active = parseActive(activeText || "");
  const state = {
    // Only known from the device's status; "" if it doesn't say.
    running: status && isFactory(status.config_id) ? DEFAULT_ID : (status && status.config_id) || "",
    powerOn: active.config,
    once: active.once,
  };
  const protection = await api.getConfigProtection();
  state.protectionReady = protection.ready;
  state.protectedIds = new Set(protection.protected);
  state.machine = machine;
  lastState = state;

  const list = $("pf-list");
  const deleted = await api.getDeletedConfigs();
  const deletedIds = new Set(deleted.deleted.map(p => p.id));
  const visible = configs.filter(p => !deletedIds.has(p.id));
  if (!deleted.deleted.length) restoring = false;
  $("pf-restore").hidden = !deleted.deleted.length;
  $("pf-restore").textContent = restoring ? "Back to Configs" : "Legacy Config Cleanup";
  // Factory and user Configs without a category share the first grid.
  const groups = groupConfigs(restoring ? [] : visible);
  const first = section("");
  if (groups.length && !groups[0].category) {
    for (const p of groups.shift().configs) {
      first.grid.appendChild(configCard(p, state, configActions(p)));
    }
  }
  list.appendChild(first.frag);
  for (const group of groups) {
    const sec = section(group.category);
    for (const p of group.configs) {
      sec.grid.appendChild(configCard(p, state, configActions(p)));
    }
    list.appendChild(sec.frag);
  }
  if (!deleted.ready) {
    list.appendChild(el("p", "msg err", "Deletion metadata needs recovery. Config changes are suspended."));
  } else if (restoring && deleted.deleted.length) {
    const sec = section("Legacy Deleted Configs");
    for (const item of deleted.deleted) {
      const box = el("article", "pf-card");
      box.appendChild(el("div", "pf-name", item.name || item.id));
      box.appendChild(el("p", "", "Legacy entry: " + item.id));
      const remove = el("button", "btn", "Delete Permanently");
      remove.addEventListener("click", () => changeDeleted({id:item.id,name:item.name || item.id}, true));
      box.appendChild(remove);
      if (state.protectionReady && state.protectedIds.has(item.id)) {
        const protect = el("button", "btn", "Protected: On");
        protect.addEventListener("click", () => changeProtection({id:item.id,name:item.name || item.id}, false));
        box.appendChild(protect);
      }
      sec.grid.appendChild(box);
    }
    list.appendChild(sec.frag);
  }
  if (restoring && deleted.ready && !deleted.deleted.length) list.appendChild(el("p", "msg", "No legacy entries."));

  if (!configs.length) {
    setMsg("No configs yet. Make one on the E64 menu: Configs → New " +
           "config from current settings.");
  } else {
    setMsg("");
  }
}

export function initConfigs() {
  $("pf-restore").addEventListener("click", () => { if (loading) return; restoring = !restoring; loadConfigs(); });
  $("pf-refresh").addEventListener("click", loadConfigs);
  $("pf-restart-close").addEventListener("click", hideRestart);
}
