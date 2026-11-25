import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source = fs.readFileSync('src/webui/assets/js/dashboard.js', 'utf8');
const html = fs.readFileSync('src/webui/assets/index.html', 'utf8');
const elements = new Map();
function $(id) {
  assert.ok(html.includes('id="' + id + '"'), 'Missing dashboard element ' + id);
  if (!elements.has(id)) {
    const classes = new Set();
    elements.set(id, {
      style: {}, firstElementChild: {}, setAttribute() {}, addEventListener() {},
      classList: {
        contains: name => classes.has(name),
        toggle(name, on) { if (on) classes.add(name); else classes.delete(name); },
      },
    });
  }
  return elements.get(id);
}
let status;
let states;
let driveCalls = 0;
let pendingDrive;
let driveError;
const browserEvents = {};
const documentEvents = {};
let nextPoll;
let nextTimer = 0;
const timers = new Map();
const context = vm.createContext({
  $, fmtUptime: String, setMachine() {}, updateHotkeys() {},
  AbortController,
  navigator: { onLine: true },
  document: { hidden: false, addEventListener: (name, fn) => { documentEvents[name] = fn; } },
  window: { addEventListener: (name, fn) => { browserEvents[name] = fn; } },
  setTimeout(fn, ms) {
    if (ms >= 5000) nextPoll = ms;
    const id = ++nextTimer;
    timers.set(id, { fn, ms });
    return id;
  },
  clearTimeout(id) { timers.delete(id); },
  api: {
    getStatus: async () => status,
    getDriveActivity: async (signal) => {
      driveCalls++;
      if (driveError) throw driveError;
      if (pendingDrive) return pendingDrive(signal);
      return states;
    },
  }
});
vm.runInContext(source.replace(/^import .*;$/gm, '').replace(/^export /gm, ''), context);

async function poll(fields) {
  status = fields;
  await context.pollStatus();
  assert.equal(nextPoll, 5000);
  assert.equal($('sys-state').textContent, 'System Online');
}
await poll({ virtual_modem_address: '$D700', ftdi_rs232: '9600,N,8,1', audio_output: 'HDMI', fan_on: true, soc_temp_c: 52 });
assert.equal($('d-modem-address').textContent, 'D700');
assert.equal($('d-ftdi').textContent, '9600,N,8,1');
assert.equal($('d-audio').textContent, 'HDMI');
assert.equal($('d-temp').textContent, '52.0 °C');
assert.equal($('d-fan').hidden, false);
assert.equal($('d-fan').style.color, 'var(--green)');
assert.match($('d-fan').title, /no rotation feedback/);

await poll({ virtual_modem_address: '$DF80', ftdi_rs232: '1200,E,7,2', audio_output: 'Analog', fan_on: false });
assert.equal($('d-modem-address').textContent, 'DF80');
assert.equal($('d-ftdi').textContent, '1200,E,7,2');
assert.equal($('d-audio').textContent, 'Analog');
assert.equal($('d-fan').style.color, 'var(--c64-medium-gray)');
assert.equal($('d-tempmeter').hidden, false);
assert.equal($('d-temp').textContent, 'Unavailable');

await poll({ virtual_modem_address: 'Off', ftdi_rs232: 'Off', audio_output: 'Auto', fan_on: null });
assert.equal($('d-modem-address').textContent, 'Off');
assert.equal($('d-ftdi').textContent, 'Off');
assert.equal($('d-audio').textContent, 'Auto');
assert.equal($('d-fan').hidden, true);
await poll({});
for (const id of ['d-modem-address', 'd-ftdi', 'd-audio']) assert.equal($(id).textContent, '—');
assert.doesNotMatch(html, /id="fan-settings"/);
assert.ok(fs.readFileSync('src/webui/assets/js/api.js', 'utf8').includes('{ headers: WEB_HEADER }'));
console.log('PASS dashboard polling renders updated modem, FTDI and audio settings, missing and off states, temperature, and fan indicator');

context.initDashboard();
const driveState = () => [8, 9, 10, 11].map(unit => $("drive-led-" + unit).classList.contains("active"));
const timersAt = ms => [...timers].filter(([, timer]) => timer.ms === ms);
function fire(ms) {
  const entries = timersAt(ms);
  assert.equal(entries.length, 1, "Expected one timer at " + ms + " ms");
  const [id, timer] = entries[0];
  timers.delete(id);
  return timer.fn();
}
async function sample(values) {
  states = values;
  await fire(250);
}

await poll({ drives: [4040, 0, 8250, 0] });
await sample([1, 7, 1, 11]);
assert.deepEqual(driveState(), [false, true, false, true]);
assert.equal($("drive-led-9").title, "Drive 8 mechanism 1 activity: active");
assert.equal($("drive-led-11").title, "Drive 10 mechanism 1 activity: active");
await sample([5, 4, 1, 8]);
assert.deepEqual(driveState(), [true, false, false, false]);
await sample([5, 4, 1, 8]);
assert.deepEqual(driveState(), [true, false, false, false]);
fire(350);
assert.deepEqual(driveState(), [false, false, false, false]);
await sample([5, 4, 7, 8]);
assert.deepEqual(driveState(), [false, false, true, false]);

let finish;
let signal;
pendingDrive = requestSignal => {
  signal = requestSignal;
  return new Promise(resolve => { finish = resolve; });
};
const inFlight = fire(250);
const calls = driveCalls;
context.syncDriveActivity();
assert.equal(timersAt(250).length, 0);
$("view-dashboard").hidden = true;
context.syncDriveActivity();
assert.equal(signal.aborted, true);
assert.deepEqual(driveState(), [false, false, false, false]);
$("view-dashboard").hidden = false;
context.syncDriveActivity();
assert.equal(timersAt(250).length, 0);
finish([7, 7, 7, 7]);
await inFlight;
assert.equal(driveCalls, calls);
assert.deepEqual(driveState(), [false, false, false, false]);
pendingDrive = null;
await sample([9, 4, 9, 8]);
assert.deepEqual(driveState(), [false, false, false, false]);

context.document.hidden = true;
documentEvents.visibilitychange();
assert.equal(timersAt(250).length, 0);
context.document.hidden = false;
documentEvents.visibilitychange();
assert.equal(timersAt(250).length, 1);
context.navigator.onLine = false;
browserEvents.offline();
assert.equal(timersAt(250).length, 0);
context.navigator.onLine = true;
browserEvents.online();
await new Promise(setImmediate);
assert.equal(timersAt(250).length, 1);

driveError = Error("disconnected");
await fire(250);
assert.equal(timersAt(250).length, 0);
driveError = null;
await fire(5000);
await sample([11, 4, 9, 8]);
assert.deepEqual(driveState(), [true, false, false, false]);

pendingDrive = requestSignal => new Promise((resolve, reject) => {
  requestSignal.addEventListener("abort", () => reject(Error("aborted")));
});
const timedOut = fire(250);
fire(2000);
await timedOut;
assert.equal(timersAt(250).length, 0);
assert.deepEqual(driveState(), [false, false, false, false]);
await fire(5000);
assert.equal(timersAt(250).length, 1);
console.log('PASS drive activity timer, both dual pairs, disabled slots, pulse hold, route/visibility cancellation, offline, failure, timeout and recovery');
