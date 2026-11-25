#!/usr/bin/env python3
"""Firefox raw-cartridge dialog assertions, real keys and post-completion captures.

Run: python3 tools/raw_cartridge_test/dialog_browser_check.py
Self-test without a browser/network: add --self-test.
Uses Firefox's built-in Marionette protocol and Python's standard library only.
No device endpoints, SD access, production edits or firmware builds.
"""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread, Lock
import argparse
import base64
import datetime
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[2]
VIEWPORTS = [(1280, 1024), (1280, 900), (390, 780)]

SCRIPT = r'''
import {chooseRawCartridge} from '/js/raw_cartridge.js';
const checks=[];const check=(name,pass)=>{checks.push({name,pass:!!pass});window.__rawTest.checks=checks;window.__rawTest.last_assertion=name;};
const tick=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
const rect=e=>e.getBoundingClientRect();
const opener=document.getElementById('opener');opener.focus();
const open=(name='game.rom')=>{const result=chooseRawCartridge(name,16384);return {result,d:document.querySelector('dialog[open]')};};
window.__rawOpenForKeyboard=()=>{
 const t=open();window.__rawChoice={pending:true};
 t.result.then(value=>{window.__rawChoice=value;});return true;
};
window.__rawFinish=async extra=>{
 try{
  checks.push(...extra);open();await tick();
  await window.__rawReport({phase:'complete',checks,capture_ready:true});
 }catch(error){await window.__rawReport({phase:'javascript_error',checks,error:String(error.stack||error),capture_ready:false});}
};
try{
 await window.__rawReport({phase:'assertions',checks,capture_ready:false});
 let t=open();await document.fonts.ready;await tick();
 check('requested viewport width',innerWidth===Number(new URL(location.href).searchParams.get('width')));
 const d=t.d,box=rect(d),head=d.querySelector('.e64-popup-header'),title=head.querySelector('h2');
 check('exact heading',title.textContent==='Load Raw Cartridge');
 check('existing orange heading',getComputedStyle(title).color===getComputedStyle(document.documentElement).getPropertyValue('--section-heading').trim()||getComputedStyle(title).color==='rgb(221, 136, 85)');
 check('existing thick header separator',getComputedStyle(head).borderBottomWidth==='4px');
 check('compact width',box.width<=400.5&&box.width>=Math.min(300,innerWidth*.9));
 check('compact height',box.height<520);
 check('centered horizontally',Math.abs((box.left+box.right)/2-innerWidth/2)<2);
 check('centered vertically',Math.abs((box.top+box.bottom)/2-innerHeight/2)<2);
 check('no dialog scroll/clipping',d.scrollWidth<=d.clientWidth+1&&d.scrollHeight<=d.clientHeight+1);
 const spans=[...d.querySelectorAll('.raw-cartridge-file span')];
 check('filename and size',spans[0].textContent==='game.rom'&&spans[1].textContent==='16 KB');
 check('same information row',Math.abs(rect(spans[0]).top-rect(spans[1]).top)<2&&rect(spans[0]).right<=rect(spans[1]).left);
 check('exact warning text',JSON.stringify([...d.querySelectorAll('.raw-cartridge-notes p')].map(p=>p.textContent))===JSON.stringify(['For cartridge ROMs only.\nSize does not identify cartridge type.','Loading replaces the attached cartridge.\nA failed load may detach it.']));
 const select=d.querySelector('select');check('suggested type and explicit Ultimax',select.value==='16k'&&[...select.options].some(o=>o.value==='ultimax'&&!o.disabled));
 const label=d.querySelector('label');check('label associated with select',label.htmlFor===select.id&&label.textContent==='Cartridge Type');
 const buttons=[...d.querySelectorAll('.dialog-buttons button')];
 check('Cancel initially focused',document.activeElement===buttons[0]);
 check('orange primary action',buttons[1].textContent==='Load & Run'&&buttons[1].classList.contains('btn-primary'));
 for(const e of [title,head.querySelector('button'),...spans,select,...buttons]){const b=rect(e);check('control within dialog',b.left>=box.left&&b.right<=box.right&&b.bottom<=box.bottom);}
 select.focus();check('select keyboard focus',document.activeElement===select);select.value='ultimax';d.querySelector('form').requestSubmit();check('explicit selection submits',await t.result==='ultimax');check('focus restored after confirmation',document.activeElement===opener);
 t=open();t.d.querySelector('.dialog-buttons button').click();check('Cancel returns no choice',await t.result===null);
 t=open();t.d.querySelector('.popup-close').click();check('Close returns no choice',await t.result===null);
 t=open();t.d.dispatchEvent(new Event('cancel',{cancelable:true}));check('native cancel event returns no choice',await t.result===null);check('focus restored after cancel',document.activeElement===opener);
 t=open('A'.repeat(220)+'.rom');await tick();check('long filename readable without horizontal clipping',t.d.scrollWidth<=t.d.clientWidth+1&&t.d.querySelector('.raw-cartridge-file span').textContent.length===224);const longSpans=t.d.querySelectorAll('.raw-cartridge-file span');check('long filename keeps size column clear',rect(longSpans[0]).right<=rect(longSpans[1]).left&&rect(longSpans[1]).right<=rect(t.d).right);t.d.close();await t.result;
 window.__rawOpenForKeyboard();await tick();
 await window.__rawReport({phase:'keyboard',checks,capture_ready:false});
}catch(error){await window.__rawReport({phase:'javascript_error',checks:[...checks,{name:String(error),pass:false}],error:String(error.stack||error),capture_ready:false});}
'''


BOOTSTRAP = r'''
const runId=new URL(location.href).searchParams.get('run');
window.__rawTest={run_id:runId,phase:'loading',checks:[],capture_ready:false};
window.__rawReport=async payload=>{
 if(window.__rawTest.phase==='javascript_error'&&payload.phase!=='javascript_error')return;
 window.__rawTest={...payload,run_id:runId};
 try{
  const reply=await fetch('/__results?run='+encodeURIComponent(runId),{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(window.__rawTest)});
  if(!reply.ok)throw Error('Result HTTP '+reply.status);
 }catch(error){window.__rawTest={...window.__rawTest,phase:'javascript_error',capture_ready:false,error:'Completion reporting failed: '+error};}
};
window.addEventListener('error',event=>{
 window.__rawReport({phase:'javascript_error',checks:window.__rawTest.checks||[],capture_ready:false,
  error:String(event.error?.stack||event.message||('Resource failed: '+(event.target?.src||event.target?.href||'unknown'))) });
},true);
window.addEventListener('unhandledrejection',event=>{
 window.__rawReport({phase:'javascript_error',checks:window.__rawTest.checks||[],capture_ready:false,error:String(event.reason?.stack||event.reason)});
});
'''


class BrowserStartupError(RuntimeError):
    pass


class CompletionTimeout(RuntimeError):
    pass


class BrowserExited(RuntimeError):
    pass


class MarionetteError(RuntimeError):
    def __init__(self, error):
        self.error = error if isinstance(error, dict) else {"message": str(error)}
        super().__init__(json.dumps(self.error))


class Marionette:
    """The small protocol surface this test needs; no third-party client."""
    def __init__(self, connection):
        self.socket = connection
        self.serial = 0
        self.deadline = None
        hello = self.read_frame()
        if hello.get("marionetteProtocol") != 3:
            raise BrowserStartupError("Unsupported Marionette greeting: " + repr(hello))

    def receive(self, count):
        chunks = bytearray()
        while len(chunks) < count:
            data = self.socket.recv(count - len(chunks))
            if not data:
                raise BrowserExited("Firefox closed its automation connection")
            chunks.extend(data)
        return bytes(chunks)

    def read_frame(self):
        prefix = bytearray()
        while True:
            char = self.receive(1)
            if char == b":":
                break
            if not char.isdigit() or len(prefix) >= 9:
                raise RuntimeError("Invalid Marionette message length")
            prefix.extend(char)
        count = int(prefix)
        if not 0 < count <= 32 * 1024 * 1024:
            raise RuntimeError("Marionette message exceeds the test limit")
        return json.loads(self.receive(count).decode("utf-8"))

    def command(self, name, parameters=None):
        if self.deadline is not None:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise CompletionTimeout("Automation command deadline expired: " + name)
            self.socket.settimeout(min(10, remaining))
        self.serial += 1
        payload = json.dumps([0, self.serial, name, parameters or {}], ensure_ascii=False).encode("utf-8")
        self.socket.sendall(str(len(payload)).encode("ascii") + b":" + payload)
        while True:
            reply = self.read_frame()
            if not isinstance(reply, list) or len(reply) != 4 or reply[0] != 1 or reply[1] != self.serial:
                raise RuntimeError("Unexpected Marionette response: " + repr(reply))
            if reply[2]:
                raise MarionetteError(reply[2])
            return reply[3]

    def execute(self, script, *args):
        result = self.command("WebDriver:ExecuteScript", {
            "script": script, "args": list(args), "sandbox": None,
            "newSandbox": False, "filename": "raw-cartridge-test", "line": 1,
        })
        return result.get("value") if isinstance(result, dict) and set(result) == {"value"} else result

    def key(self, value, shift=False):
        actions = []
        if shift:
            actions.append({"type": "keyDown", "value": "\ue008"})
        actions += [{"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]
        if shift:
            actions.append({"type": "keyUp", "value": "\ue008"})
        self.command("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "raw-dialog-keys", "actions": actions}]})


class Reports:
    def __init__(self):
        self.lock = Lock()
        self.runs = {}
        self.history = []

    def register(self, run_id):
        with self.lock:
            self.runs[run_id] = None

    def accept(self, run_id, report):
        with self.lock:
            if run_id not in self.runs or report.get("run_id") != run_id:
                return False
            # A late report from another viewport must never satisfy this run.
            self.runs[run_id] = report
            self.history.append({"run_id": run_id, "phase": report.get("phase"), "time": time.monotonic()})
            return True

    def get(self, run_id):
        with self.lock:
            value = self.runs.get(run_id)
            return dict(value) if value else None


def handler_class(reports):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "src/webui/assets"), **kwargs)

        def log_message(self, *_args):
            pass

        def do_GET(self):
            request = urllib.parse.urlsplit(self.path)
            if request.path != "/preview":
                return super().do_GET()
            query = urllib.parse.parse_qs(request.query)
            run_id = query.get("run", [""])[0]
            with reports.lock:
                known = run_id in reports.runs
            if not known:
                self.send_error(400, "Unknown test run")
                return
            page = ('<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">'
                    '<link rel="stylesheet" href="/style.css"><button id="opener" class="btn">Load Cartridge...</button>'
                    '<script>' + BOOTSTRAP + '</script><script type="module">' + SCRIPT + '</script>')
            data = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            request = urllib.parse.urlsplit(self.path)
            if request.path != "/__results":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Invalid report length")
                report = json.loads(self.rfile.read(length))
                run_id = urllib.parse.parse_qs(request.query).get("run", [""])[0]
                if not isinstance(report, dict) or not reports.accept(run_id, report):
                    raise ValueError("Unknown or mismatched run ID")
            except (ValueError, TypeError):
                self.send_error(400, "Invalid test report")
                return
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")
    return Handler


def report_status(report):
    if report.get("phase") == "javascript_error":
        return "javascript_error"
    if report.get("phase") != "complete" or report.get("capture_ready") is not True:
        raise CompletionTimeout("No explicit completed/capture-ready report")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError("Completion report contains no assertions")
    return "passed" if all(item.get("pass") is True for item in checks) else "assertion_failed"


def wait_report(client, process, reports, run_id, phases, deadline):
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise BrowserExited("Firefox exited before completing the assertions")
        report = reports.get(run_id)
        if report and report.get("phase") in phases | {"javascript_error"}:
            return report
        # Also expose import/runtime/report-delivery errors that could not POST.
        state = client.execute("return window.__rawTest || null;")
        if state and state.get("run_id") == run_id and state.get("phase") == "javascript_error":
            return state
        time.sleep(0.05)
    last = reports.get(run_id)
    raise CompletionTimeout("Completion deadline expired; last phase: " + str(last.get("phase") if last else "no report"))


def set_viewport(client, width, height):
    """Set the content viewport, accounting for Firefox's browser chrome."""
    for _ in range(5):
        dimensions = client.execute("return {width:innerWidth,height:innerHeight};")
        if dimensions == {"width": width, "height": height}:
            return dimensions
        rect = client.command("WebDriver:GetWindowRect")
        if isinstance(rect, dict) and set(rect) == {"value"}:
            rect = rect["value"]
        client.command("WebDriver:SetWindowRect", {
            "width": max(100, rect["width"] + width - dimensions["width"]),
            "height": max(100, rect["height"] + height - dimensions["height"]),
        })
    # Narrow desktop windows can have a minimum browser-chrome width. Remove
    # that restriction in this isolated test profile, never in the E64 page.
    client.command("Marionette:SetContext", {"value": "chrome"})
    try:
        client.execute("document.documentElement.style.setProperty('min-width','0px','important'); document.documentElement.style.setProperty('min-height','0px','important');")
    finally:
        client.command("Marionette:SetContext", {"value": "content"})
    for _ in range(3):
        dimensions = client.execute("return {width:innerWidth,height:innerHeight};")
        if dimensions == {"width": width, "height": height}:
            break
        rect = client.command("WebDriver:GetWindowRect")
        if isinstance(rect, dict) and set(rect) == {"value"}:
            rect = rect["value"]
        client.command("WebDriver:SetWindowRect", {
            "width": max(100, rect["width"] + width - dimensions["width"]),
            "height": max(100, rect["height"] + height - dimensions["height"]),
        })
    # Do not weaken the original viewport assertion if Firefox cannot resize.
    return client.execute("return {width:innerWidth,height:innerHeight};")


def keyboard_checks(client, deadline):
    checks = []
    def check(name, value):
        checks.append({"name": name, "pass": bool(value)})
    def focus():
        return client.execute("return {text:document.activeElement.textContent,type:document.activeElement.tagName};")
    def choice():
        until = min(deadline, time.monotonic() + 3)
        while time.monotonic() < until:
            result = client.execute("return {ready:window.__rawChoice===null||typeof window.__rawChoice==='string',value:window.__rawChoice};")
            if result["ready"]:
                return result
            time.sleep(0.05)
        return {"ready": False}
    client.key("\ue004")  # TAB: Cancel -> Load & Run
    check("real Tab focuses Load & Run", focus()["text"] == "Load & Run")
    client.key("\ue004", shift=True)
    check("real Shift+Tab returns to Cancel", focus()["text"] == "Cancel")
    client.key("\ue004", shift=True)
    check("real Shift+Tab reaches cartridge selector", focus()["type"] == "SELECT")
    client.key("\ue015")  # ARROW DOWN: 16K -> Ultimax
    check("real arrow key selects Ultimax", client.execute("return document.querySelector('dialog[open] select').value;") == "ultimax")
    client.key("\ue004")
    client.key("\ue004")
    check("real Tab returns to Load & Run", focus()["text"] == "Load & Run")
    client.key("\ue007")  # ENTER
    result = choice()
    check("real Enter confirms chosen type", result.get("ready") and result.get("value") == "ultimax")
    check("real Enter restores opener focus", client.execute("return document.activeElement.id==='opener';"))
    client.execute("document.querySelectorAll('dialog[open]').forEach(d=>d.close()); window.__rawOpenForKeyboard(); return true;")
    client.key("\ue00c")  # ESCAPE invokes the actual browser cancel behavior
    result = choice()
    check("real Escape cancels without a type", result.get("ready") and result.get("value") is None)
    check("real Escape restores opener focus", client.execute("return document.activeElement.id==='opener';"))
    client.execute("document.querySelectorAll('dialog[open]').forEach(d=>d.close()); window.__rawOpenForKeyboard(); return true;")
    client.key("\ue007")  # Enter on initially focused Cancel is safe.
    result = choice()
    check("real Enter on Cancel makes no selection", result.get("ready") and result.get("value") is None)
    client.execute("document.querySelectorAll('dialog[open]').forEach(d=>d.close()); return true;")
    client.command("WebDriver:ReleaseActions")
    return checks


def capture(client, report, path):
    # This precondition is intentionally strict, including for failed assertions.
    if report.get("phase") != "complete" or report.get("capture_ready") is not True or not report.get("checks"):
        raise RuntimeError("Refusing screenshot before explicit completed assertions")
    value = client.command("WebDriver:TakeScreenshot", {"full": False, "scroll": False})
    if isinstance(value, dict):
        value = value["value"]
    data = base64.b64decode(value, validate=True)
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Firefox did not return a PNG screenshot")
    path.write_bytes(data)
    return struct.unpack(">II", data[16:24])


def connect_firefox(process, port, deadline):
    last_error = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise BrowserStartupError("Firefox exited during startup: " + str(process.returncode))
        try:
            connection = socket.create_connection(("127.0.0.1", port), timeout=0.5)
        except OSError as error:
            last_error = error
            time.sleep(0.1)
            continue
        connection.settimeout(max(0.05, min(10, deadline - time.monotonic())))
        try:
            return Marionette(connection)
        except Exception:
            connection.close()
            raise
    raise BrowserStartupError("Firefox Marionette startup deadline expired: " + str(last_error))


def run_viewport(out, reports, server, width, height, timeout, startup_timeout):
    run_id = uuid.uuid4().hex
    reports.register(run_id)
    record = {"width": width, "height": height, "run_id": run_id, "status": "browser_startup_failed", "checks": [], "screenshot": None}
    process = client = None
    started = False
    profile = out / f"profile-{width}x{height}"
    profile.mkdir()
    log_path = out / f"firefox-{width}x{height}.log"
    record["browser_log"] = str(log_path)
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        preferences = {
            "marionette.port": port, "marionette.enabled": True,
            "browser.shell.checkDefaultBrowser": False, "browser.aboutwelcome.enabled": False,
            "browser.startup.homepage_override.mstone": "ignore", "browser.startup.page": 0,
            "browser.tabs.warnOnClose": False, "layout.css.devPixelsPerPx": "1.0",
            "accessibility.tabfocus": 7,
        }
        (profile / "user.js").write_text("\n".join("user_pref(" + json.dumps(k) + ", " + json.dumps(v) + ");" for k, v in preferences.items()) + "\n")
        with log_path.open("w") as log:
            process = subprocess.Popen([
                "firefox", "--headless", "--no-remote", "--marionette", "--remote-allow-system-access",
                "--profile", str(profile), "about:blank",
            ], stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "MOZ_HEADLESS_WIDTH": str(width + 256),
                     "MOZ_HEADLESS_HEIGHT": str(height + 256)})
        startup_deadline = time.monotonic() + startup_timeout
        client = connect_firefox(process, port, startup_deadline)
        client.deadline = startup_deadline
        client.command("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"pageLoadStrategy": "none"}}})
        record["actual_viewport"] = set_viewport(client, width, height)
        started = True
        deadline = time.monotonic() + timeout
        client.deadline = deadline
        client.command("WebDriver:Navigate", {"url": f"http://127.0.0.1:{server.server_port}/preview?width={width}&run={run_id}"})
        report = wait_report(client, process, reports, run_id, {"keyboard"}, deadline)
        if report.get("phase") == "keyboard":
            extra = keyboard_checks(client, deadline)
            extra.append({"name": "requested viewport height", "pass": client.execute("return innerHeight;") == height})
            client.execute("window.__rawFinish(arguments[0]); return true;", extra)
            report = wait_report(client, process, reports, run_id, {"complete"}, deadline)
        record["checks"] = report.get("checks", [])
        record["phase"] = report.get("phase")
        record["status"] = report_status(report)
        if report.get("error"):
            record["error"] = report["error"]
        if report.get("phase") == "complete":
            client.deadline = time.monotonic() + 10
            path = out / f"raw-cartridge-{width}x{height}.png"
            dimensions = capture(client, report, path)
            record["screenshot"] = str(path)
            record["checks"].append({"name": "screenshot matches requested viewport", "pass": dimensions == (width, height)})
            if record["status"] == "passed" and dimensions != (width, height):
                record["status"] = "assertion_failed"
    except CompletionTimeout as error:
        record.update(status="completion_timeout", error=str(error))
    except (socket.timeout, TimeoutError) as error:
        record.update(status="completion_timeout" if started else "browser_startup_failed", error=str(error))
    except BrowserExited as error:
        record.update(status="browser_exited" if started else "browser_startup_failed", error=str(error))
    except MarionetteError as error:
        kind = error.error.get("error", "")
        status = "browser_startup_failed" if not started else (
            "javascript_error" if kind == "javascript error" else
            "completion_timeout" if "timeout" in kind else "browser_automation_failed")
        record.update(status=status, error=str(error))
    except Exception as error:
        record.update(status="browser_automation_failed" if started else "browser_startup_failed", error=str(error))
    finally:
        latest = reports.get(run_id)
        if started and client and record["status"] not in {"passed", "assertion_failed"}:
            try:
                client.deadline = time.monotonic() + 2
                partial = client.execute("return window.__rawTest || null;")
                if partial and partial.get("run_id") == run_id:
                    if len(partial.get("checks", [])) > len(record["checks"]):
                        record["checks"] = partial["checks"]
                    record["last_assertion"] = partial.get("last_assertion")
                    record["phase"] = partial.get("phase")
            except Exception:
                pass
        if latest and not record["checks"]:
            record["checks"] = latest.get("checks", [])
            record["phase"] = latest.get("phase")
        if client:
            try:
                client.deadline = None
                client.socket.settimeout(2)
                client.command("WebDriver:DeleteSession")
            except Exception:
                pass
            client.socket.close()
        if process:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            record["browser_exit_code_after_cleanup"] = process.returncode
        record["phase_history"] = [event for event in reports.history if event["run_id"] == run_id]
    return record


def self_test():
    """Offline protocol/lifecycle tests. Never starts Firefox or binds a socket."""
    from unittest.mock import patch
    checks = []
    def check(name, passed):
        if not passed:
            raise AssertionError(name)
        checks.append({"name": name, "pass": True})
    def frame(value):
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        return str(len(data)).encode() + b":" + data
    class FakeSocket:
        def __init__(self, incoming=b""):
            self.incoming = incoming
            self.sent = []
        def recv(self, count):
            # Exercise partial reads, including multibyte UTF-8 payloads.
            chunk, self.incoming = self.incoming[:min(count, 3)], self.incoming[min(count, 3):]
            return chunk
        def settimeout(self, _timeout):
            pass
        def sendall(self, data):
            self.sent.append(data)
        def close(self):
            pass
    connection = FakeSocket(frame({"marionetteProtocol": 3}) + frame([1, 1, None, {"value": "✓"}]))
    client = Marionette(connection)
    check("framed UTF-8/partial Marionette replies", client.execute("return '✓';") == "✓")
    length, payload = connection.sent[0].split(b":", 1)
    check("outgoing byte length and command", int(length) == len(payload) and json.loads(payload)[2] == "WebDriver:ExecuteScript")
    client = Marionette(FakeSocket(frame({"marionetteProtocol": 3}) + frame([1, 1, {"error": "javascript error", "message": "boom"}, None])))
    try:
        client.command("WebDriver:ExecuteScript")
        raise AssertionError("expected JavaScript protocol error")
    except MarionetteError as error:
        check("JavaScript protocol errors retained", error.error["error"] == "javascript error")
    client = Marionette(FakeSocket(frame({"marionetteProtocol": 3})))
    client.deadline = time.monotonic() - 1
    try:
        client.command("WebDriver:Navigate")
        raise AssertionError("expected expired command refusal")
    except CompletionTimeout:
        check("expired commands never send or block", not client.socket.sent)
    recorder = Marionette.__new__(Marionette)
    actions = []
    recorder.command = lambda name, args: actions.append((name, args))
    recorder.key("\ue004", shift=True)
    key_actions = actions[0][1]["actions"][0]["actions"]
    check("real Shift+Tab action releases both keys", actions[0][0] == "WebDriver:PerformActions" and [a["type"] for a in key_actions] == ["keyDown", "keyDown", "keyUp", "keyUp"])
    registry = Reports()
    registry.register("one")
    registry.register("two")
    complete = {"run_id": "one", "phase": "complete", "capture_ready": True, "checks": [{"name": "layout", "pass": True}]}
    check("mismatched/stale run rejected", not registry.accept("two", complete) and registry.get("two") is None)
    check("matching explicit completion accepted", registry.accept("one", complete))
    check("pass classification", report_status(complete) == "passed")
    failed = {**complete, "checks": [{"name": "clipping", "pass": False}]}
    check("individual assertion failure classification", report_status(failed) == "assertion_failed")
    check("JavaScript-error classification", report_status({"phase": "javascript_error"}) == "javascript_error")
    try:
        report_status({"phase": "keyboard", "capture_ready": False})
        raise AssertionError("expected incomplete report refusal")
    except CompletionTimeout:
        check("incomplete phase never passes", True)
    try:
        report_status({"phase": "complete", "capture_ready": True, "checks": []})
        raise AssertionError("expected empty assertion refusal")
    except RuntimeError:
        check("empty completion report never passes", True)
    class LiveProcess:
        returncode = None
        def poll(self):
            return self.returncode
        def terminate(self):
            self.returncode = 0
        def wait(self, timeout=None):
            return self.returncode
    try:
        wait_report(None, LiveProcess(), registry, "two", {"complete"}, time.monotonic() - 1)
        raise AssertionError("expected bounded timeout")
    except CompletionTimeout:
        check("completion deadline is bounded", True)
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aA1cAAAAASUVORK5CYII=")
    class FakeClient:
        def __init__(self):
            self.socket = FakeSocket()
            self.commands = []
        def command(self, name, params=None):
            self.commands.append(name)
            if name == "WebDriver:TakeScreenshot":
                return {"value": base64.b64encode(png).decode()}
        def execute(self, *args):
            return True
    with tempfile.TemporaryDirectory(prefix="e64-browser-harness-self-test-") as directory:
        output = Path(directory)
        driver = FakeClient()
        try:
            capture(driver, {"phase": "keyboard", "capture_ready": False}, output / "premature.png")
            raise AssertionError("expected premature capture refusal")
        except RuntimeError:
            check("no screenshot before completion", not driver.commands and not (output / "premature.png").exists())
        check("screenshot after completion", capture(driver, complete, output / "done.png") == (1, 1))
        class Probe:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
            def bind(self, *_args):
                pass
            def getsockname(self):
                return ("127.0.0.1", 2828)
        from types import SimpleNamespace
        server = SimpleNamespace(server_port=1234)
        for outcome in ["passed", "assertion_failed", "javascript_error", "completion_timeout", "browser_startup_failed"]:
            folder = output / outcome
            folder.mkdir()
            driver = FakeClient()
            process = LiveProcess()
            terminal = {**complete, "checks": [{"name": "layout", "pass": outcome != "assertion_failed"}]}
            if outcome == "javascript_error":
                terminal = {"phase": "javascript_error", "error": "boom", "checks": []}
            report_side_effect = [terminal] if outcome == "javascript_error" else [{"phase": "keyboard"}, terminal]
            if outcome == "completion_timeout":
                report_side_effect = CompletionTimeout("fixture timeout")
            with patch("socket.socket", return_value=Probe()), \
                 patch("subprocess.Popen", side_effect=FileNotFoundError("fixture Firefox missing") if outcome == "browser_startup_failed" else None, return_value=process), \
                 patch(__name__ + ".connect_firefox", return_value=driver), \
                 patch(__name__ + ".set_viewport", return_value={"width": 1, "height": 1}), \
                 patch(__name__ + ".keyboard_checks", return_value=[{"name": "real keyboard fixture", "pass": True}]), \
                 patch(__name__ + ".wait_report", side_effect=report_side_effect):
                record = run_viewport(folder, Reports(), server, 1, 1, 1, 1)
            check("lifecycle classification: " + outcome, record["status"] == outcome)
            took_screenshot = "WebDriver:TakeScreenshot" in driver.commands
            check("completion-gated capture: " + outcome, took_screenshot == (outcome in {"passed", "assertion_failed"}))
    print("PASS:", len(checks), "isolated harness protocol/lifecycle checks; no Firefox, network or SD access")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--timeout", type=float, default=45, help="Bounded page completion time in seconds")
    parser.add_argument("--startup-timeout", type=float, default=20)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.timeout <= 0 or args.startup_timeout <= 0:
        parser.error("timeouts must be positive")
    out = ROOT / "build/raw-cartridge-dialog-firefox" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out.mkdir(parents=True)
    reports = Reports()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class(reports))
    except OSError as error:
        records = [{"width": w, "height": h, "status": "blocked", "reason": "Local HTTP listener unavailable: " + str(error), "checks": [], "screenshot": None} for w, h in VIEWPORTS]
        (out / "results.json").write_text(json.dumps(records, indent=2) + "\n")
        print("BLOCKED:", error)
        print("Results:", out)
        return 2
    Thread(target=server.serve_forever, daemon=True).start()
    records = []
    try:
        for width, height in VIEWPORTS:
            record = run_viewport(out, reports, server, width, height, args.timeout, args.startup_timeout)
            records.append(record)
            print(record["status"].upper(), width, height, flush=True)
            for assertion in record["checks"]:
                print("  " + ("PASS " if assertion.get("pass") else "FAIL ") + assertion.get("name", "Unnamed assertion"), flush=True)
            if record.get("error"):
                print("  ERROR:", record["error"], flush=True)
            (out / "results.json").write_text(json.dumps(records, indent=2) + "\n")
    finally:
        server.shutdown()
        server.server_close()
    print("Screenshots and individual results:", out)
    return 0 if records and all(r["status"] == "passed" for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
