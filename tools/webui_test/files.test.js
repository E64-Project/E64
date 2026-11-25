// Exercise the real Files/API modules with controllable network responses.
class Element {
  constructor(fragment = false) {
    this.children = []; this.value = ""; this.listeners = {}; this.fragment = fragment;
    this.hidden = false; this.style = {}; this.dataset = {}; this.attrs = {};
    const classes = new Set();
    this.classList = { add: (...xs) => xs.forEach((x) => classes.add(x)),
      remove: (...xs) => xs.forEach((x) => classes.delete(x)),
      contains: (x) => classes.has(x),
      toggle: (x, on) => { on = on === undefined ? !classes.has(x) : on;
        if (on) classes.add(x); else classes.delete(x); return on; } };
  }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return (this.text || "") + this.children.map((c) => c.textContent).join(""); }
  appendChild(child) { if (child.fragment) this.children.push(...child.children); else this.children.push(child); return child; }
  append(...children) { children.forEach((c) => this.appendChild(c)); }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, fn) { this.listeners[k] = fn; }
}
const flush = async () => { for (let i = 0; i < 12; ++i) await Promise.resolve(); };

export async function runTests() {
  let passed = 0, failed = 0;
  const log = [];
  let requests, elements, stored;
  const globals = ["document", "localStorage", "location", "history", "fetch"];
  const originals = globals.map((key) => Object.getOwnPropertyDescriptor(globalThis, key));
  function fixture() {
    requests = []; elements = new Map(); stored = new Map();
    globalThis.document = { getElementById: (id) => {
      if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id);
    }, createElement: () => new Element(), createDocumentFragment: () => new Element(true),
    querySelector: () => document.getElementById("nav-files"), body: new Element() };
    globalThis.localStorage = { getItem: (k) => stored.get(k) || null, setItem: (k, v) => stored.set(k, v) };
    globalThis.location = { hash: "#/files" };
    globalThis.history = { replaceState: (_state, _title, hash) => { location.hash = hash; } };
    globalThis.fetch = (url, options) => new Promise((resolve) => requests.push({ url, options, resolve }));
  }
  fixture();
  const files = await import("../../src/webui/assets/js/files.js");
  const { setMachine } = await import("../../src/webui/assets/js/machine.js");
  const api = await import("../../src/webui/assets/js/api.js");
  const el = (id) => document.getElementById(id);
  const eq = (a, b) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(JSON.stringify(a) + " != " + JSON.stringify(b)); };
  const ok = (a) => { if (!a) throw new Error("assertion failed"); };
  const reply = (i, data, status = 200) => requests[i].resolve({ ok: status < 400, status,
    json: async () => data, text: async () => typeof data === "string" ? data : JSON.stringify(data) });
  const listing = (name, path = "/", vol = "USB") => ({ vol, path, entries: name ? [{ name, size: 1, dir: false }] : [] });
  const volumes = (...ids) => ({ volumes: ids.map((id) => ({ id })) });
  async function test(name, fn) {
    fixture(); files.selectFilesVolume("USB");
    try { await fn(); passed++; } catch (e) { failed++; log.push("FAIL " + name + "\n     " + e.stack); }
  }
  try {
    await test("BASIC creation follows real machine capability across volumes and folders", async () => {
      for (const basic of ["", "v2", ""]) {
        setMachine({ machine: "C64", caps: { run: [], basic } });
        for (const vol of ["SD", "USB", "USB2", "USB3"]) {
          files.selectFilesVolume(vol);
          for (const path of ["/", "/demos"]) {
            const index = requests.length, task = files.loadDir(path);
            reply(index, listing(null, path, vol)); await task;
            eq(el("fb-newbasic").hidden, basic === "");
          }
        }
      }
    });
    await test("icons follow metadata at every depth; names and Actions stay intact", async () => {
      const rows=[{name:'ROMs.d64',dir:true,size:0},{name:'deep.ROM',dir:true,size:0},{name:'Demo.D64',dir:false,size:123},{name:'actual.bin',dir:false,size:10}];
      for(const path of ['/', '/ROMs.d64/deep.ROM']){
        const index=requests.length,task=files.loadDir(path);reply(index,{vol:'USB',path,entries:rows});await task;
        const rendered=el('fb-rows').children;
        eq(rendered.length,4);
        for(const row of rendered){const nameCell=row.children[0],wrap=nameCell.children[0],icon=wrap.children[0],name=wrap.children[1];
          ok(rows.some(e=>e.name===name.textContent));
          eq(icon.attrs.width,'16');eq(icon.attrs.height,'16');
          eq(icon.dataset.fileType,rows.find(e=>e.name===name.textContent).dir?'directory':name.textContent.endsWith('.D64')?'floppy':'unknown');
          if(icon.dataset.fileType==='directory')ok(name.href.includes(encodeURIComponent(name.textContent)));
          ok(row.children[3].children[0].textContent==='Actions ▾');
        }
      }
    });
    await test("newer directory beats older response", async () => {
      const old = files.loadDir("/old"), newer = files.loadDir("/new");
      reply(1, listing("new.txt", "/new")); await newer;
      reply(0, listing("old.txt", "/old")); await old;
      ok(el("fb-rows").textContent.includes("new.txt")); ok(!el("fb-rows").textContent.includes("old.txt"));
      ok(el("fb-crumbs").textContent.includes("new"));
    });
    await test("stale failure does not overwrite success", async () => {
      const old = files.loadDir("/old"), newer = files.loadDir("/new");
      reply(1, listing("new.txt", "/new")); await newer;
      reply(0, "gone", 503); await old;
      eq(el("fb-status").textContent, "");
    });
    await test("volume change invalidates pending response", async () => {
      const old = files.loadDir("/"); files.selectFilesVolume("SD");
      reply(0, listing("old.txt")); await old;
      ok(!el("fb-rows").textContent.includes("old.txt"));
    });
    await test("refresh preserves valid volume and directory", async () => {
      files.selectFilesVolume("USB2"); location.hash = "#/files/games";
      const task = files.refreshFiles(); eq(requests[0].url, "/api/volumes");
      reply(0, volumes("SD", "USB2")); await flush();
      ok(requests[1].url.includes("vol=USB2")); ok(requests[1].url.includes("path=%2Fgames"));
      reply(1, listing("game.d64", "/games", "USB2")); await task;
      eq(location.hash, "#/files/games"); eq(el("fb-vol-USB2").hidden, false); eq(el("fb-vol-USB").hidden, true);
      eq(requests.length, 2); await flush(); eq(requests.length, 2);
    });
    await test("removed volume falls back once to available root", async () => {
      location.hash = "#/files/old"; const task = files.refreshFiles();
      reply(0, volumes("SD")); await flush();
      ok(requests[1].url.includes("vol=SD")); ok(requests[1].url.includes("path=%2F&"));
      reply(1, listing("settings.txt", "/", "SD")); await task;
      eq(location.hash, "#/files"); eq(stored.get("bmc64-files-volume"), "SD"); eq(requests.length, 2);
    });
    await test("missing subdirectory falls back to root", async () => {
      location.hash = "#/files/missing"; const task = files.refreshFiles();
      reply(0, volumes("USB")); await flush(); reply(1, "no such directory", 404); await flush();
      ok(requests[2].url.includes("path=%2F&")); reply(2, listing("root.txt")); await task;
      eq(location.hash, "#/files"); ok(el("fb-rows").textContent.includes("root.txt"));
    });
    await test("mid-stream filesystem error rejects partial listing", async () => {
      const task = files.loadDir("/");
      reply(0, { ...listing("partial.txt"), error: "directory read failed", error_status: 503 }); await task;
      ok(el("fb-status").textContent.includes("directory read failed"));
      ok(!el("fb-rows").textContent.includes("partial.txt")); ok(!el("fb-status").textContent.includes("Empty folder"));
    });
    await test("unavailable root reports an error, not empty", async () => {
      const task = files.loadDir("/"); reply(0, "directory unavailable", 503); await task;
      ok(el("fb-status").textContent.includes("503")); eq(requests.length, 1);
    });
    await test("overlapping refresh responses cannot restore old volumes", async () => {
      const old = files.refreshFiles(), newer = files.refreshFiles();
      reply(1, volumes("USB", "SD")); await flush(); reply(2, listing("latest.txt")); await newer;
      reply(0, volumes("USB3")); await old;
      ok(el("fb-rows").textContent.includes("latest.txt")); eq(el("fb-vol-USB3").hidden, true); eq(requests.length, 3);
    });
    await test("navigation during volume refresh remains selected", async () => {
      const refresh = files.refreshFiles(); files.selectFilesVolume("SD"); location.hash = "#/files/new";
      const nav = files.loadDir("/new"); reply(1, listing("new.txt", "/new", "SD")); await nav;
      reply(0, volumes("USB", "SD")); await refresh;
      ok(el("fb-crumbs").textContent.includes("new")); ok(el("fb-rows").textContent.includes("new.txt")); eq(requests.length, 2);
    });
    await test("no storage gives explicit error without listing request", async () => {
      const task = files.refreshFiles(); reply(0, volumes()); await task;
      eq(el("fb-status").textContent, "No available storage volumes."); eq(requests.length, 1);
    });
    await test("refresh volume error remains visible", async () => {
      const task = files.refreshFiles(); reply(0, "offline", 503); await task;
      ok(el("fb-status").textContent.includes("Could not refresh drives")); eq(requests.length, 1);
    });
    await test("capacity is explicitly requested and never cached by HTTP", async () => {
      const lightweight = api.getVolumes(), capacity = api.getVolumes(true);
      eq(requests[0].url, "/api/volumes"); eq(requests[1].url, "/api/volumes?capacity=1");
      eq(requests[0].options.cache, "no-store"); reply(0, volumes("USB")); reply(1, volumes("USB"));
      await Promise.all([lightweight, capacity]);
    });
    await test("initial volume response cannot override newer Refresh", async () => {
      files.initFiles(); const task = el("fb-refresh").listeners.click();
      reply(1, volumes("USB", "SD")); await flush(); reply(2, listing("fresh.txt")); await task;
      reply(0, volumes("USB3")); await flush();
      eq(el("fb-vol-USB3").hidden, true); ok(el("fb-rows").textContent.includes("fresh.txt"));
    });
    await test("initial volume snapshot cannot displace a newer valid folder", async () => {
      files.initFiles(); location.hash = "#/files/new";
      const nav = files.loadDir("/new"); reply(1, listing("new.txt", "/new")); await nav;
      reply(0, volumes("SD")); await flush();
      eq(location.hash, "#/files/new"); eq(el("fb-vol-USB").hidden, false);
      ok(el("fb-rows").textContent.includes("new.txt")); eq(requests.length, 2);
    });
    await test("refresh invalidates an older listing before checking volumes", async () => {
      const old = files.loadDir("/old"), refresh = files.refreshFiles();
      reply(0, listing("old.txt", "/old")); await old; ok(!el("fb-rows").textContent.includes("old.txt"));
      reply(1, volumes("USB")); await flush(); reply(2, listing("fresh.txt")); await refresh;
      ok(el("fb-rows").textContent.includes("fresh.txt"));
    });
    await test("Datasette LOAD uses TAP name selection across volumes and returns only after attachment", async () => {
      setMachine({ machine: "C64", caps: { run: ["tap"], basic: "v2" } });
      files.initFiles(); reply(0, volumes("SD", "USB", "USB2", "USB3")); await flush();
      el("tape-load").listeners.click(); eq(el("fb-tape-cancel").hidden, false);
      for (const vol of ["SD", "USB", "USB2", "USB3"]) {
        files.selectFilesVolume(vol); location.hash = "#/files/tapes";
        const index = requests.length, task = files.loadDir("/tapes");
        reply(index, listing("Selected.TAP", "/tapes", vol)); await task;
        const link = el("fb-rows").children[0].children[0].children[0].children[1];
        eq(link.title, "Load Tape Selected.TAP");
      }
      const link = el("fb-rows").children[0].children[0].children[0].children[1];
      const index = requests.length;
      link.listeners.click({ preventDefault() {} }); await flush();
      ok(requests[index].url.includes("/api/fs/load-tape?vol=USB3&path=%2Ftapes%2FSelected.TAP"));
      eq(location.hash, "#/files/tapes");
      reply(index, { request_id: 19 }); await flush();
      reply(index+1, { serial:19, pending:0, error:0, attached:1, mode:0 }); await flush();
      eq(location.hash, "#/datasette"); eq(el("fb-tape-cancel").hidden, true);
      ok(requests.slice(index).every(r=>! /autostart|control/.test(r.url)));
      files.beginTapeSelection();el("fb-tape-cancel").listeners.click();eq(location.hash,"#/datasette");
    });
    await test("valid empty directory still displays empty", async () => {
      const task = files.loadDir("/"); reply(0, listing(null)); await task;
      eq(el("fb-status").textContent, "");
    });
  } finally {
    globals.forEach((key, i) => { if (originals[i]) Object.defineProperty(globalThis, key, originals[i]); else delete globalThis[key]; });
  }
  return { passed, failed, log };
}
