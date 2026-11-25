#!/usr/bin/env node
// Runs the web UI's JavaScript tests (BASIC tokeniser, config files).
//
//     node tools/webui_test/run_tests.mjs
//
// Needs Node.js 22.12 or newer (older versions cannot load the ES modules in
// src/webui/assets/js, which are plain .js files). `source get_gnu_toolchain.sh`
// puts a suitable Node.js on PATH. Exit status is 0 if every test passed.

const [major, minor] = process.versions.node.split(".").map(Number);
if (major < 22 || (major === 22 && minor < 12)) {
  console.error("Node.js 22.12 or newer is required (this is " + process.version + ").");
  console.error("Run: source get_gnu_toolchain.sh");
  process.exit(2);
}

let passed = 0;
let failed = 0;
for (const file of ["./basic.test.js", "./configs.test.js", "./files.test.js", "./ui.test.js"]) {
  const result = await (await import(file)).runTests();
  for (const line of result.log) console.log(line);
  passed += result.passed;
  failed += result.failed;
}
await import("./file_icons_test.mjs");
await import("./ui_polish_test.mjs");
await import("./instructions_help_test.mjs");
await import("./hardware_help_test.mjs");
await import("../fan_test/web_test.mjs");
await import("./issues_batch06_test.mjs");
await import("./issues_batch07_test.mjs");
await import("./datasette_transport_test.mjs");
await import("./load_tape_test.mjs");
await import("./jiffydos_commands_test.mjs");
await import("./final_ui_polish_test.mjs");
await import("./unified_ui_test.mjs");
await import("./about_e64_test.mjs");
await import("./hotkeys_layout_repair_test.mjs");
await import("./round1_text_test.mjs");
await import("./round1_reference_test.mjs");
await import("./round3_test.mjs");
await import("./round3_dialog_assertion_test.mjs");
await import("./round3_touchup_test.mjs");
await import("./round3_final_webui_test.mjs");
await import("./basic_browser_regression_test.mjs");
console.log(passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);

