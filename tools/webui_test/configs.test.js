// Tests for reading the config files in the web UI
// (src/webui/assets/js/configs_data.js), against the same rules as the
// device's parser (src/configs, tools/configs_test).
//
// A plain ES module with no dependencies. run_tests.mjs runs it under Node.js;
// runTests() returns { passed, failed, log }.

import {
  activeWithout, cleanName, groupConfigs, idValid, machineDetail, machineLabel,
  parseActive, parseKv, parseConfig, CONFIG_FILES, settingsFile,
  withName, MAX_CONFIG_NAME, DEFAULT_ID,
} from "../../src/webui/assets/js/configs_data.js";

export function runTests() {
  const log = [];
  let passed = 0;
  let failed = 0;

  function test(name, fn) {
    try {
      fn();
      passed++;
    } catch (e) {
      failed++;
      log.push("FAIL " + name + "\n     " + String(e.message).split("\n").join("\n     "));
    }
  }
  function eq(got, want, what) {
    const g = JSON.stringify(got);
    const w = JSON.stringify(want);
    if (g !== w) throw new Error((what ? what + ": " : "") + "got  " + g + "\nwant " + w);
  }

  test("key=value lines", () => {
    const kv = parseKv("  name =  My Game  \n# name=comment\nnot a pair\n=x\n" +
                       "machine=C64\r\nname=Last\n");
    eq(kv.get("name"), "Last", "last repeated key wins");
    eq(kv.get("machine"), "C64", "CRLF");
    eq(kv.has("# name"), false, "comment");
    eq(kv.size, 2);
  });

  test("ids", () => {
    eq(idValid("geos-2"), true);
    eq(idValid("GEOS"), false);
    eq(idValid("my game"), false);
    eq(idValid(""), false);
    eq(idValid("a".repeat(32)), true);
    eq(idValid("a".repeat(33)), false);
    eq(idValid(undefined), false);
  });

  test("config.txt", () => {
    const p = parseConfig("elite", "name=Elite\nmachine=C64/PAL/HDMI\n" +
      "category=Games\nstart=once\ndisk_9=SD:/games/save.d64\n" +
      "disk_08=SD:/x.d64\ndisk_12=SD:/y.d64\nautostart=SD:/games/elite.d64\n");
    eq(p.name, "Elite");
    eq(p.machine, "C64/PAL/HDMI");
    eq(p.category, "Games");
    eq(p.start, "once");
    eq(p.disks, ["", "SD:/games/save.d64", "", ""], "only disk_8..disk_11");
    eq(p.autostart, "SD:/games/elite.d64");
    eq(parseConfig("x", "name=x\nmachine=C64\nstart=Once\n").start, "switch");
  });

  test("shared Config display and input constants", () => {
    eq(MAX_CONFIG_NAME, 32);
    eq(DEFAULT_ID, "_factory-ntsc");
    eq(idValid("main"), false);
  });

  test("invalid configs", () => {
    eq(parseConfig("a", "machine=C64\n"), null, "no name");
    eq(parseConfig("a", "name=A\n"), null, "no machine");
    eq(parseConfig("UPPER", "name=A\nmachine=C64\n"), null, "bad id");
    eq(parseConfig("main", "name=A\nmachine=C64\n"), null, "main isn't a config");
    eq(parseConfig("a", "name=" + "n".repeat(40) + "\nmachine=C64\n"),
       null, "overlong metadata rejected");
  });

  test("active.txt", () => {
    eq(parseActive("config=geos\nonce=elite\nmain_machine=C64/PAL/HDMI\n"),
       { config: "geos", once: "elite" });
    eq(parseActive(""), { config: "_factory-ntsc", once: "" }, "empty");
    eq(parseActive("config=GEOS\nonce=Elite!\n"),
       { config: "_factory-ntsc", once: "" }, "typos are ignored");
  });

  test("retired selection falls back", () => {
    eq(parseActive("config=main\n"), {config: DEFAULT_ID, once: ""});
  });

  test("machine labels", () => {
    eq(machineLabel("C64/PAL/HDMI/VICE 720p@50Hz"), "C64");
    eq(machineLabel(""), "");
    eq(machineDetail("C64 / PAL / HDMI / VICE 720p@50Hz"),
       "PAL · HDMI · VICE 720p @ 50 Hz");
    eq(machineDetail("C64"), "");
  });

  test("grouping", () => {
    const p = (name, category) => ({ name, category });
    const groups = groupConfigs([p("zork", "Games"), p("Elite", "Games"),
                                  p("Jiffy", ""), p("basic", ""), p("GEOS", "Apps")]);
    // Categories in the order their first config sorts, as in the menu.
    eq(groups.map((g) => g.category), ["", "Games", "Apps"]);
    eq(groups[0].configs.map((x) => x.name), ["basic", "Jiffy"]);
    eq(groups[1].configs.map((x) => x.name), ["Elite", "zork"]);
    eq(groupConfigs([]), []);
  });

  test("names", () => {
    eq(cleanName("  My GEOS  "), "My GEOS");
    eq(cleanName("   "), "");
    eq(cleanName(null), "");
    eq(cleanName("a\nb"), "a b", "one line");
    eq(cleanName("n".repeat(32)), "n".repeat(32), "maximum accepted");
    eq(cleanName("n".repeat(33)), "", "overflow rejected, never truncated");
    eq(cleanName("é".repeat(16)), "é".repeat(16), "32 UTF-8 bytes");
    eq(cleanName("é".repeat(17)), "", "UTF-8 byte overflow");
    eq(parseConfig("x", "name=" + "x".repeat(33) + "\nmachine=C64\n"), null, "invalid stored name rejected");
    eq(cleanName("x".repeat(17) + "  y"), "x".repeat(17) + "  y", "not silently shortened");
  });

  test("rename keeps the rest of config.txt", () => {
    eq(withName("# mine\nname=Old\nmachine=C64\nname=Older\n", "New"),
       "# mine\nname=New\nmachine=C64\n", "repeats removed");
    eq(withName("  name = Old\r\nmachine=C64\r\n", "New"),
       "name=New\r\nmachine=C64\r\n", "CRLF kept");
    eq(withName("machine=C64", "New"), "name=New\nmachine=C64\n", "no name yet");
    const back = parseConfig("x", withName("name=Old\nmachine=C64\n", "New"));
    eq(back.name, "New");
  });

  test("active.txt after a delete", () => {
    eq(activeWithout("config=geos\nonce=geos\nmain_machine=C64\n", "geos"),
       "config=_factory-ntsc\nmain_machine=C64\n");
    eq(activeWithout("config=elite\nonce=geos\n", "geos"), "config=elite\n");
    eq(activeWithout("config=elite\n", "geos"), null, "not mentioned");
    eq(activeWithout("config=geos-2\n", "geos"), null, "only that id");
    eq(activeWithout("config = geos \r\n", "geos"), "config=_factory-ntsc\r\n");
  });

  test("settings files", () => {
    eq(settingsFile("C64/PAL/HDMI"), "settings-c64.txt");
    eq(settingsFile("Plus4Emu"), "settings.txt");
    eq(settingsFile("VIC20 / PAL"), "settings.txt");
    eq(settingsFile(""), "settings.txt");
    for (const f of ["settings.txt", "settings-c64.txt",
                     "vice.in~", "config.txt.bak"]) {
      eq(CONFIG_FILES.includes(f), true, f);
    }
    for (const f of ["settings-c128.txt", "settings-vic20.txt",
                     "settings-plus4.txt", "settings-plus4emu.txt",
                     "settings-pet.txt"]) {
      eq(CONFIG_FILES.includes(f), false, f);
    }
    eq(CONFIG_FILES.includes("my-notes.txt"), false);
  });

  return { passed, failed, log };
}
