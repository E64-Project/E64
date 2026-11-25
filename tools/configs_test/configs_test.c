// Tests for src/configs, against the behaviour in docs/CONFIGS.md.
// Config files are created in a temporary folder that stands in for the SD
// card (tools/sdcard/sd_fs_posix.c, given the folder in SD_TEST_ROOT).

#define _POSIX_C_SOURCE 200809L

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "../../src/sdcard/sd_fs.h"
#include "configs_internal.h"

// The temporary folder standing in for the SD card.
static char card_root[512];

static int failures;

#define CHECK(expr)                                                         \
   do {                                                                     \
      if (!(expr)) {                                                        \
         fprintf(stderr, "%s:%d: FAILED: %s\n", __FILE__, __LINE__, #expr); \
         failures++;                                                        \
      }                                                                     \
   } while (0)

#define CHECK_STR(actual, expected)                                         \
   do {                                                                     \
      const char *a_ = (actual);                                            \
      const char *e_ = (expected);                                          \
      if (a_ == NULL || strcmp(a_, e_) != 0) {                              \
         fprintf(stderr, "%s:%d: FAILED: %s is \"%s\", expected \"%s\"\n",  \
                 __FILE__, __LINE__, #actual, a_ ? a_ : "(null)", e_);      \
         failures++;                                                        \
      }                                                                     \
   } while (0)

// Existing selection payload remains exact; new writers append a checksum.
static void check_active_text(const char *expected) {
 char text[2048];
 int n=sd_read_file("/configs/active.txt",text,sizeof(text));
 size_t len=strlen(expected);
 CHECK(n >= (int)len && !strncmp(text,expected,len));
 if(n>(int)len) CHECK(!strncmp(text+len,"selection_crc=",14) && n==(int)len+23);
 ActiveFile af; CHECK(active_file_read(&af)==CONFIGS_OK);
}
#define CHECK_ACTIVE(expected) check_active_text(expected)

// ---- Test card ----

static void remove_tree(const char *path) {
   DIR *dir = opendir(path);
   if (dir != NULL) {
      struct dirent *entry;
      while ((entry = readdir(dir)) != NULL) {
         if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
         }
         char child[1024];
         snprintf(child, sizeof(child), "%s/%s", path, entry->d_name);
         remove_tree(child);
      }
      closedir(dir);
      rmdir(path);
   } else {
      unlink(path);
   }
}

// Empties the test card.
static void fresh_card(void) {
   DIR *dir = opendir(card_root);
   if (dir != NULL) {
      struct dirent *entry;
      while ((entry = readdir(dir)) != NULL) {
         if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
         }
         char child[1024];
         snprintf(child, sizeof(child), "%s/%s", card_root, entry->d_name);
         remove_tree(child);
      }
      closedir(dir);
   }
}

// Offline fixture provisioning may seed immutable Main files. Runtime writes
// in tests still go through sd_fs and the production protection policy.
static void write_file(const char *path, const char *text) {
   char full[1024];snprintf(full,sizeof(full),"%s%s",card_root,path);
   for(char *p=full+1;*p;p++)if(*p=='/'){*p=0;mkdir(full,0700);*p='/';}
   FILE *f=fopen(full,"wb");CHECK(f!=NULL);
   if(f){CHECK(fwrite(text,1,strlen(text),f)==strlen(text));CHECK(fclose(f)==0);}
}

static const char *read_file(const char *path) {
   static char text[4096];
   if (sd_read_file(path, text, sizeof(text)) < 0) {
      return NULL;
   }
   return text;
}

static int exists(const char *path) {
   return sd_stat(path, NULL, NULL) == 0;
}

static void make_config(const char *id, const char *text) {
   char path[256];
   snprintf(path, sizeof(path), "/configs/%s/config.txt", id);
   write_file(path, text);
}

// ---- key=value parser ----

typedef struct {
   int count;
   char keys[16][64];
   char values[16][256];
} Collected;

static void collect(void *ctx, const char *key, const char *value) {
   Collected *c = (Collected *)ctx;
   if (c->count < 16) {
      snprintf(c->keys[c->count], sizeof(c->keys[0]), "%s", key);
      snprintf(c->values[c->count], sizeof(c->values[0]), "%s", value);
      c->count++;
   }
}

static Collected parse(const char *text) {
   char copy[1024];
   Collected c;
   memset(&c, 0, sizeof(c));
   snprintf(copy, sizeof(copy), "%s", text);
   pkv_parse(copy, collect, &c);
   return c;
}

static void test_kv_parse(void) {
   Collected c = parse("name=GEOS\nmachine=C64\n");
   CHECK(c.count == 2);
   CHECK_STR(c.keys[0], "name");
   CHECK_STR(c.values[0], "GEOS");
   CHECK_STR(c.keys[1], "machine");
   CHECK_STR(c.values[1], "C64");

   // Spaces around keys and values are ignored, spaces inside values kept.
   c = parse("  name =  My Game  \n\tmachine\t=\tC64/PAL/HDMI/VICE 720p@50Hz\t\n");
   CHECK(c.count == 2);
   CHECK_STR(c.keys[0], "name");
   CHECK_STR(c.values[0], "My Game");
   CHECK_STR(c.values[1], "C64/PAL/HDMI/VICE 720p@50Hz");

   // Windows line endings.
   c = parse("name=GEOS\r\nmachine=C64\r\n");
   CHECK(c.count == 2);
   CHECK_STR(c.values[0], "GEOS");
   CHECK_STR(c.values[1], "C64");

   // Comment lines, blank lines, and lines without '=' are skipped.
   c = parse("# a comment\n\n   \n  # indented comment\nno equals here\nname=x\n");
   CHECK(c.count == 1);
   CHECK_STR(c.keys[0], "name");

   // '#' only starts a comment at the start of a line.
   c = parse("name=Game #2\n");
   CHECK(c.count == 1);
   CHECK_STR(c.values[0], "Game #2");

   // Only the first '=' splits.
   c = parse("description=a=b=c\n");
   CHECK(c.count == 1);
   CHECK_STR(c.values[0], "a=b=c");

   // An empty key is skipped; an empty value is passed on.
   c = parse("=value\nname=\n");
   CHECK(c.count == 1);
   CHECK_STR(c.keys[0], "name");
   CHECK_STR(c.values[0], "");

   // No newline at the end.
   c = parse("name=last");
   CHECK(c.count == 1);
   CHECK_STR(c.values[0], "last");

   // Nothing at all.
   c = parse("");
   CHECK(c.count == 0);
}

static void test_kv_append(void) {
   char buf[64];
   int len = 0;
   buf[0] = '\0';
   CHECK(pkv_append(buf, sizeof(buf), &len, "name", "GEOS") == 0);
   CHECK(pkv_append(buf, sizeof(buf), &len, "empty", "") == 0);
   CHECK(pkv_append(buf, sizeof(buf), &len, "none", NULL) == 0);
   CHECK_STR(buf, "name=GEOS\n");
   CHECK(len == (int)strlen(buf));

   // Values never span lines.
   CHECK(pkv_append(buf, sizeof(buf), &len, "d", "a\nb\rc") == 0);
   CHECK_STR(buf, "name=GEOS\nd=a b c\n");

   // What doesn't fit isn't written.
   int before = len;
   CHECK(pkv_append(buf, sizeof(buf), &len, "long",
                    "0123456789012345678901234567890123456789") == -1);
   CHECK(len == before);
   CHECK_STR(buf, "name=GEOS\nd=a b c\n");

   char out[8];
   pkv_copy(out, sizeof(out), "abcdefghij");
   CHECK_STR(out, "abcdefg");
   pkv_copy(out, sizeof(out), "a\nb");
   CHECK_STR(out, "a b");
}

// ---- config.txt ----

static void test_config_parse(void) {
   char text[1024];
   ConfigFile pf;

   snprintf(text, sizeof(text),
            "# GEOS\n"
            "name=GEOS 2.0\n"
            "description=GEOS with a 1764 REU\n"
            "category=Applications\n"
            "machine=C64/PAL/HDMI/VICE 720p@50Hz\n"
            "start=once\n"
            "disk_8=/disks/geos/GEOS64.D81\n"
            "disk_9=/disks/geos/APPS.D81\n"
            "disk_11=/disks/data.d64\n"
            "autostart=/disks/geos/GEOS64.D81\n"
            "unknown=ignored\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_OK);
   CHECK_STR(pf.info.name, "GEOS 2.0");
   CHECK_STR(pf.description, "GEOS with a 1764 REU");
   CHECK_STR(pf.info.category, "Applications");
   CHECK_STR(pf.info.machine, "C64/PAL/HDMI/VICE 720p@50Hz");
   CHECK(pf.info.start == CONFIG_START_ONCE);
   CHECK_STR(pf.disks[0], "/disks/geos/GEOS64.D81");
   CHECK_STR(pf.disks[1], "/disks/geos/APPS.D81");
   CHECK_STR(pf.disks[2], "");
   CHECK_STR(pf.disks[3], "/disks/data.d64");
   CHECK_STR(pf.autostart, "/disks/geos/GEOS64.D81");

   // name and machine are required.
   snprintf(text, sizeof(text), "machine=C64\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_ERROR);
   snprintf(text, sizeof(text), "name=No machine\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_ERROR);
   snprintf(text, sizeof(text), "name=\nmachine=C64\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_ERROR);
   snprintf(text, sizeof(text), "%s", "");
   CHECK(config_file_parse(text, &pf) == CONFIGS_ERROR);

   // start defaults to switch; only "once" means once.
   snprintf(text, sizeof(text), "name=a\nmachine=C64\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_OK);
   CHECK(pf.info.start == CONFIG_START_SWITCH);
   snprintf(text, sizeof(text), "name=a\nmachine=C64\nstart=Once\n");
   config_file_parse(text, &pf);
   CHECK(pf.info.start == CONFIG_START_SWITCH);
   snprintf(text, sizeof(text), "name=a\nmachine=C64\nstart=switch\n");
   config_file_parse(text, &pf);
   CHECK(pf.info.start == CONFIG_START_SWITCH);

   // Only drives 8 to 11, spelled exactly.
   snprintf(text, sizeof(text),
            "name=a\nmachine=C64\ndisk_7=x\ndisk_12=x\ndisk_08=x\ndisk_8x=x\n"
            "disk_=x\ndisk_10=/ten.d64\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_OK);
   CHECK_STR(pf.disks[0], "");
   CHECK_STR(pf.disks[1], "");
   CHECK_STR(pf.disks[2], "/ten.d64");
   CHECK_STR(pf.disks[3], "");

   // Overlong metadata is rejected, never silently truncated.
   snprintf(text, sizeof(text),
            "name=0123456789012345678901234567890123456789\nmachine=C64\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_ERROR);

   // The last of a repeated key wins.
   snprintf(text, sizeof(text), "name=first\nname=second\nmachine=C64\n");
   config_file_parse(text, &pf);
   CHECK_STR(pf.info.name, "second");

   // Windows line endings.
   snprintf(text, sizeof(text), "name=Win\r\nmachine=C64\r\n");
   CHECK(config_file_parse(text, &pf) == CONFIGS_OK);
   CHECK_STR(pf.info.name, "Win");
   CHECK_STR(pf.info.machine, "C64");
}

static void test_config_format(void) {
   ConfigFile pf;
   memset(&pf, 0, sizeof(pf));
   strcpy(pf.info.name, "Elite");
   strcpy(pf.info.machine, "C64");
   char text[CONFIGS_MAX_FILE_LEN];

   // Empty values and the default start aren't written.
   CHECK(config_file_format(&pf, text, sizeof(text)) > 0);
   CHECK_STR(text, "name=Elite\nmachine=C64\n");

   strcpy(pf.description, "A game");
   strcpy(pf.info.category, "Games");
   pf.info.start = CONFIG_START_ONCE;
   strcpy(pf.disks[0], "/disks/elite.d64");
   strcpy(pf.disks[3], "/disks/save.d64");
   strcpy(pf.autostart, "/c64/snapshots/elite.vsf");
   CHECK(config_file_format(&pf, text, sizeof(text)) > 0);
   CHECK_STR(text,
             "name=Elite\ndescription=A game\ncategory=Games\nmachine=C64\n"
             "start=once\ndisk_8=/disks/elite.d64\ndisk_11=/disks/save.d64\n"
             "autostart=/c64/snapshots/elite.vsf\n");

   // Writing and reading back gives the same config.
   ConfigFile back;
   CHECK(config_file_parse(text, &back) == CONFIGS_OK);
   CHECK_STR(back.info.name, pf.info.name);
   CHECK_STR(back.description, pf.description);
   CHECK_STR(back.info.category, pf.info.category);
   CHECK_STR(back.info.machine, pf.info.machine);
   CHECK(back.info.start == pf.info.start);
   for (int i = 0; i < CONFIGS_NUM_DRIVES; i++) {
      CHECK_STR(back.disks[i], pf.disks[i]);
   }
   CHECK_STR(back.autostart, pf.autostart);

   // A buffer that's too small is an error, not a cut-off file.
   CHECK(config_file_format(&pf, text, 40) == CONFIGS_ERROR);
}

// ---- active.txt ----

static void test_active_parse(void) {
   char text[256];
   ActiveFile af;

   snprintf(text, sizeof(text), "%s", "");
   active_file_parse(text, &af);
   CHECK_STR(af.config, CONFIGS_FACTORY_NTSC);
   CHECK_STR(af.once, "");

   snprintf(text, sizeof(text), "config=geos\n");
   active_file_parse(text, &af);
   CHECK_STR(af.config, "geos");
   CHECK_STR(af.once, "");

   snprintf(text, sizeof(text), "# comment\r\nconfig=geos\r\nonce=elite\r\n");
   active_file_parse(text, &af);
   CHECK_STR(af.config, "geos");
   CHECK_STR(af.once, "elite");

   // Invalid ids are ignored: no paths, upper case or long names.
   snprintf(text, sizeof(text),
            "config=../system\nonce=/configs/x\n");
   active_file_parse(text, &af);
   CHECK_STR(af.config, CONFIGS_FACTORY_NTSC);
   CHECK_STR(af.once, "");
   snprintf(text, sizeof(text), "config=GEOS\nonce=%s\n",
            "a23456789012345678901234567890123");
   active_file_parse(text, &af);
   CHECK_STR(af.config, CONFIGS_FACTORY_NTSC);
   CHECK_STR(af.once, "");
   snprintf(text, sizeof(text), "config=\nonce=\n");
   active_file_parse(text, &af);
   CHECK_STR(af.config, CONFIGS_FACTORY_NTSC);
   CHECK_STR(af.once, "");
   CHECK_STR(af.bad_config, "");
   CHECK_STR(af.bad_once, "");

   // Invalid values are kept, so start-up can say what was wrong.
   snprintf(text, sizeof(text), "config=My Game\nonce=../x\n");
   active_file_parse(text, &af);
   CHECK_STR(af.config, CONFIGS_FACTORY_NTSC);
   CHECK_STR(af.once, "");
   CHECK_STR(af.bad_config, "My Game");
   CHECK_STR(af.bad_once, "../x");
}

// ---- Ids ----

static void test_ids(void) {
   CHECK(configs_id_valid("geos"));
   CHECK(configs_id_valid("vic20-pal-16k"));
   CHECK(configs_id_valid("a2345678901234567890123456789012"));
   CHECK(!configs_id_valid("a23456789012345678901234567890123"));
   CHECK(!configs_id_valid(""));
   CHECK(!configs_id_valid(NULL));
   CHECK(!configs_id_valid("GEOS"));
   CHECK(!configs_id_valid("my game"));
   CHECK(!configs_id_valid("../x"));
   CHECK(!configs_id_valid("a/b"));

   fresh_card();
   char id[CONFIGS_MAX_ID_LEN + 1];
   CHECK(configs_make_id("GEOS 2.0", id, sizeof(id)) == CONFIGS_OK);
   CHECK_STR(id, "geos-2-0");
   configs_make_id("  Elite!! ", id, sizeof(id));
   CHECK_STR(id, "elite");
   configs_make_id("PAL VIC-20 + 16K", id, sizeof(id));
   CHECK_STR(id, "pal-vic-20-16k");
   configs_make_id("Über Spiel", id, sizeof(id));
   CHECK_STR(id, "ber-spiel");
   configs_make_id("", id, sizeof(id));
   CHECK_STR(id, "config");
   configs_make_id("!!!", id, sizeof(id));
   CHECK_STR(id, "config");
   // "main" is reserved.
   configs_make_id("Main", id, sizeof(id));
   CHECK_STR(id, "main-2");

   // Ids in use get -2, -3, ...
   make_config("elite", "name=Elite\nmachine=C64\n");
   configs_make_id("Elite", id, sizeof(id));
   CHECK_STR(id, "elite-2");
   make_config("elite-2", "name=Elite\nmachine=C64\n");
   configs_make_id("ELITE", id, sizeof(id));
   CHECK_STR(id, "elite-3");

   // Up to 32 characters, including the -2.
   const char *long_name = "A very long config name for testing ids";
   configs_make_id(long_name, id, sizeof(id));
   CHECK_STR(id, "a-very-long-config-name-for-test");
   make_config(id, "name=x\nmachine=C64\n");
   configs_make_id(long_name, id, sizeof(id));
   CHECK_STR(id, "a-very-long-config-name-for-te-2");
   CHECK(strlen(id) == CONFIGS_MAX_ID_LEN);
}

// ---- Start-up and the running config ----

static void test_no_configs(void) {
   fresh_card();
   configs_boot_init("C64/PAL/HDMI");
   // Main, and nothing created on the card.
   CHECK(configs_running_is_factory());
   CHECK(!configs_in_use());
   CHECK_STR(configs_running()->id, CONFIGS_FACTORY_NTSC);
   CHECK_STR(configs_running()->name, "Default");
   CHECK_STR(configs_running()->machine, configs_factory_info(0)->machine);
   CHECK_STR(configs_boot_message(), "");
   CHECK(configs_vice_config() == NULL);
   CHECK_STR(configs_settings_file(),
             "/configs/_factory-ntsc/settings-c64.txt");
   CHECK_STR(configs_autostart(), "");
   configs_after_boot();
   configs_before_reboot();
   CHECK(!exists("/configs"));

   // Main is always in the list.
   CHECK(configs_list_open() == 1);
   CHECK_STR(configs_list_at(0)->id, CONFIGS_FACTORY_NTSC);
   CHECK(configs_list_at(3) == NULL);
   CHECK(configs_list_at(-1) == NULL);
   configs_list_close();
}

static void test_boot_config(void) {
   fresh_card();
   make_config("geos", "name=GEOS\nmachine=C64/PAL/HDMI/VICE 720p@50Hz\n");
   write_file("/configs/active.txt", "config=geos\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(!configs_running_is_factory());
   CHECK_STR(configs_running()->id, "geos");
   CHECK_STR(configs_running()->name, "GEOS");
   CHECK_STR(configs_boot_message(), "");
   CHECK_STR(configs_vice_config(), "/configs/geos/vice.ini");
   CHECK_STR(configs_settings_file(),
             "/configs/geos/settings-c64.txt");
   // The machine name is matched without regard to case.
   configs_boot_init("c64/pal/hdmi");
   CHECK_STR(configs_running()->id, "geos");

   // A missing or invalid config starts Main, with a message.
   write_file("/configs/active.txt", "config=gone\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   CHECK(strstr(configs_boot_message(), "gone") != NULL);
   make_config("broken", "name=No machine\n");
   write_file("/configs/active.txt", "config=broken\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   CHECK(configs_boot_message()[0] != '\0');

   // A config for another machine starts Main, with a message.
   make_config("vic", "name=PAL 16K\nmachine=VIC20/PAL/HDMI\n");
   write_file("/configs/active.txt", "config=vic\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   CHECK(strstr(configs_boot_message(), "PAL 16K") != NULL);
   configs_boot_init("VIC20/PAL/HDMI");
   CHECK_STR(configs_running()->id, "vic");
   configs_boot_init("VIC20/NTSC/HDMI");
   CHECK(configs_running_is_factory());

   // A typo in config= starts Main, with a message naming it.
   write_file("/configs/active.txt", "config=GEOS\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   CHECK(strstr(configs_boot_message(), "config=GEOS") != NULL);
   write_file("/configs/active.txt", "config=my game\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   CHECK(strstr(configs_boot_message(), "my game") != NULL);

   // A typo in once= is ignored with a message; the usual config starts.
   write_file("/configs/active.txt", "config=geos\nonce=Elite!\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_running()->id, "geos");
   CHECK(strstr(configs_boot_message(), "once=Elite!") != NULL);

   // A valid once wins over a typo in config=, without a message.
   make_config("elite", "name=Elite\nmachine=C64\n");
   write_file("/configs/active.txt", "config=GEOS\nonce=elite\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_running()->id, "elite");
   CHECK_STR(configs_boot_message(), "");

   // An empty value is just "not set": no message.
   write_file("/configs/active.txt", "config=\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   CHECK_STR(configs_boot_message(), "");

   // config=main is Main without a message, with configs in use.
   write_file("/configs/active.txt", "config=_factory-ntsc\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   CHECK(configs_in_use());
   CHECK_STR(configs_boot_message(), "");
}

static void test_start_once(void) {
   fresh_card();
   make_config("geos", "name=GEOS\nmachine=C64\n");
   make_config("elite", "name=Elite\nmachine=C64\n");
   write_file("/configs/active.txt", "config=geos\n");
   configs_boot_init("C64/PAL/HDMI");

   // Once is added, config is unchanged.
   CHECK(configs_start_once("elite") == CONFIGS_OK);
   CHECK_ACTIVE( "config=geos\nonce=elite\n");

   // The once config starts; once stays until after boot.
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_running()->id, "elite");
   CHECK_ACTIVE( "config=geos\nonce=elite\n");
   configs_after_boot();
   CHECK_ACTIVE( "config=geos\n");

   // A restart BMC64 asks for keeps the once config.
   configs_before_reboot();
   CHECK_ACTIVE( "config=geos\nonce=elite\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_running()->id, "elite");
   configs_after_boot();

   // The next power-on is back on GEOS.
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_running()->id, "geos");
   // A switched-to config isn't put back as once.
   configs_before_reboot();
   CHECK_ACTIVE( "config=geos\n");

   // A once config that can't start still has its entry removed.
   write_file("/configs/active.txt", "config=geos\nonce=gone\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_running_is_factory());
   configs_after_boot();
   // Main ran, so it also remembers its machine.
   CHECK_ACTIVE(
             "config=geos\n");

   // Start once from Main with no active.txt.
   fresh_card();
   make_config("elite", "name=Elite\nmachine=C64\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_start_once("elite") == CONFIGS_OK);
   CHECK_ACTIVE(
             "config=_factory-ntsc\nonce=elite\n");
}

static void test_switch_to(void) {
   fresh_card();
   make_config("geos", "name=GEOS\nmachine=C64\n");
   make_config("vic", "name=PAL 16K\nmachine=VIC20\n");
   configs_boot_init("C64/PAL/HDMI");

   // Leaving Main remembers its machine.
   CHECK(configs_switch_to("geos") == CONFIGS_OK);
   CHECK_ACTIVE(
             "config=geos\n");
   CHECK(!exists("/configs/active.new"));
   // Switching clears a pending once.
   write_file("/configs/active.txt", "config=geos\nonce=geos\n");
   CHECK(configs_switch_to(CONFIGS_FACTORY_NTSC) == CONFIGS_OK);
   CHECK_ACTIVE(
             "config=_factory-ntsc\n");

   // Missing and invalid configs aren't started.
   CHECK(configs_switch_to("gone") == CONFIGS_ERROR);
   CHECK(configs_switch_to("../x") == CONFIGS_ERROR);
   CHECK(configs_switch_to(NULL) == CONFIGS_ERROR);
   CHECK(configs_start_once("gone") == CONFIGS_ERROR);
   CHECK_ACTIVE(
             "config=_factory-ntsc\n");

   // Other machines can be chosen; the caller switches machine first.
   CHECK_STR(configs_machine_for("vic"), "VIC20");
   CHECK_STR(configs_machine_for("geos"), "");
   CHECK_STR(configs_machine_for("main"), "");
   CHECK_STR(configs_machine_for("gone"), "");
   CHECK(configs_switch_to("vic") == CONFIGS_OK);
   CHECK_ACTIVE(
             "config=vic\n");
}

static void test_safe_mode(void) {
   fresh_card();
   make_config("geos", "name=GEOS\nmachine=C64\n");
   write_file("/configs/active.txt",
              "config=geos\nonce=geos\n");

   configs_recovery_choice(1);
   configs_boot_init("C64/NTSC/HDMI");
   CHECK_ACTIVE( "config=_factory-ntsc\n");
}

// ---- The list ----

static void test_list(void) {
   fresh_card();
   make_config("zork", "name=zork\nmachine=C64\ncategory=Games\n");
   make_config("elite", "name=Elite\nmachine=C64\ncategory=Games\nstart=once\n");
   make_config("vic", "name=PAL 16K\nmachine=VIC20/PAL/HDMI/VICE 720p@50Hz\n");
   make_config("broken", "name=No machine\n");
   make_config("UPPER", "name=Bad id\nmachine=C64\n");
   make_config("main", "name=Not Main\nmachine=C64\n");
   write_file("/configs/main/c64.txt", "disk_8=/x.d64\n");
   write_file("/configs/notes.txt", "a file, not a config\n");
   write_file("/configs/active.txt", "config=_factory-ntsc\n");
   sd_mkdir("/configs/empty");
   configs_boot_init("C64/PAL/HDMI");

   // Main first, then valid configs of every machine sorted by name.
   CHECK(configs_list_open() == 4);
   CHECK_STR(configs_list_at(0)->id, CONFIGS_FACTORY_NTSC);
   CHECK_STR(configs_list_at(1)->id, "elite");
   CHECK_STR(configs_list_at(2)->id, "vic");
   CHECK_STR(configs_list_at(3)->id, "zork");
   CHECK(configs_list_at(4) == NULL);
   CHECK_STR(configs_list_at(1)->name, "Elite");
   CHECK_STR(configs_list_at(1)->category, "Games");
   CHECK(configs_list_at(1)->start == CONFIG_START_ONCE);
   CHECK_STR(configs_list_at(2)->machine, "VIC20/PAL/HDMI/VICE 720p@50Hz");
   configs_list_close();
   // Closing frees the list; Main is still there.
   CHECK_STR(configs_list_at(0)->id, CONFIGS_FACTORY_NTSC);
   CHECK(configs_list_at(2) == NULL);
   configs_list_close();

   // Lots of configs.
   fresh_card();
   for (int i = 0; i < 40; i++) {
      char id[16];
      char text[64];
      snprintf(id, sizeof(id), "p%02d", i);
      snprintf(text, sizeof(text), "name=Config %02d\nmachine=C64\n", i);
      make_config(id, text);
   }
   CHECK(configs_list_open() == 41);
   CHECK_STR(configs_list_at(40)->id, "p39");
   configs_list_close();
}

// ---- Create, rename, delete ----

static void test_create(void) {
   fresh_card();
   configs_boot_init("C64/PAL/HDMI");
   char id[CONFIGS_MAX_ID_LEN + 1];
   // Main's new configs are for what booted.
   CHECK(configs_create("  My GEOS  ", id, sizeof(id)) == CONFIGS_OK);
   CHECK_STR(id, "my-geos");
   CHECK_STR(read_file("/configs/my-geos/config.txt"),
             "name=My GEOS\nmachine=C64/PAL/HDMI\n");
   // No active.txt yet: creating doesn't switch.
   CHECK(!exists("/configs/active.txt"));

   CHECK(configs_create("My GEOS", id, sizeof(id)) == CONFIGS_OK);
   CHECK_STR(id, "my-geos-2");
   CHECK(configs_create("   ", id, sizeof(id)) == CONFIGS_ERROR);
   CHECK(configs_create("", id, sizeof(id)) == CONFIGS_ERROR);

   // UTF-8 uses the same byte bound as Web validation (no partial sequence).
   char utf8[CONFIGS_MAX_NAME_LEN + 1];
   for (int i = 0; i < CONFIGS_MAX_NAME_LEN / 2; ++i) { utf8[2*i]=(char)0xc3;utf8[2*i+1]=(char)0xa9; }
   utf8[CONFIGS_MAX_NAME_LEN]=0;
   CHECK(configs_create(utf8, id, sizeof(id)) == CONFIGS_OK);
   ConfigFile unicode_pf;CHECK(config_file_read(id, &unicode_pf) == CONFIGS_OK);
   CHECK_STR(unicode_pf.info.name, utf8);

   // A new config made in a config copies its machine entry.
   make_config("pal", "name=PAL\nmachine=C64/PAL/HDMI/VICE 720p@50Hz\n");
   write_file("/configs/active.txt", "config=pal\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_create("Copy", id, sizeof(id)) == CONFIGS_OK);
   CHECK_STR(read_file("/configs/copy/config.txt"),
             "name=Copy\nmachine=C64/PAL/HDMI/VICE 720p@50Hz\n");

   // The same full native/storage limit is accepted; overflows are rejected.
   char max_name[CONFIGS_MAX_NAME_LEN + 1];
   memset(max_name, 'N', CONFIGS_MAX_NAME_LEN); max_name[CONFIGS_MAX_NAME_LEN] = 0;
   CHECK(configs_create(max_name, id, sizeof(id)) == CONFIGS_OK);
   ConfigFile pf;
   CHECK(config_file_read(id, &pf) == CONFIGS_OK);
   CHECK_STR(pf.info.name, max_name);
   char over[CONFIGS_MAX_NAME_LEN + 2];
   memset(over, 'X', CONFIGS_MAX_NAME_LEN + 1); over[CONFIGS_MAX_NAME_LEN + 1] = 0;
   CHECK(configs_create(over, id, sizeof(id)) == CONFIGS_ERROR);
   CHECK(!exists("/configs/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"));
   char metadata[128]; snprintf(metadata, sizeof(metadata), "name=%s\nmachine=C64\n", over);
   CHECK(config_file_parse(metadata, &pf) == CONFIGS_ERROR);
   memset(&pf, 0, sizeof(pf));memset(pf.info.name, 'x', sizeof(pf.info.name));
   CHECK(config_file_format(&pf, metadata, sizeof(metadata)) == CONFIGS_ERROR);

}

static void test_rename(void) {
   fresh_card();
   make_config("geos", "name=GEOS\nmachine=C64\ncategory=Apps\n"
                        "disk_8=/disks/geos.d81\n");
   write_file("/configs/active.txt", "config=geos\n");
   configs_boot_init("C64/PAL/HDMI");

   // Only the name changes; the id and other keys stay.
   CHECK(configs_rename_running(" GEOS 2.0 ") == CONFIGS_OK);
   CHECK_STR(configs_running()->name, "GEOS 2.0");
   CHECK_STR(configs_running()->id, "geos");
   ConfigFile pf;
   CHECK(config_file_read("geos", &pf) == CONFIGS_OK);
   CHECK_STR(pf.info.name, "GEOS 2.0");
   CHECK_STR(pf.info.category, "Apps");
   CHECK_STR(pf.disks[0], "/disks/geos.d81");
   CHECK(!exists("/configs/geos-2-0"));

   CHECK(configs_rename_running("") == CONFIGS_ERROR);
   CHECK(configs_rename_running("  ") == CONFIGS_ERROR);
   CHECK_STR(configs_running()->name, "GEOS 2.0");

   char max_name[CONFIGS_MAX_NAME_LEN + 1];
   memset(max_name, 'R', CONFIGS_MAX_NAME_LEN);max_name[CONFIGS_MAX_NAME_LEN]=0;
   CHECK(configs_rename_running(max_name) == CONFIGS_OK);
   CHECK_STR(configs_running()->name, max_name);
   char over[CONFIGS_MAX_NAME_LEN + 2];memset(over,'Z',sizeof(over)-1);over[sizeof(over)-1]=0;
   CHECK(configs_rename_running(over) == CONFIGS_ERROR);
   CHECK_STR(configs_running()->name, max_name);

   // Rename a non-running Config without changing the running identity.
   make_config("other", "name=Other\nmachine=C64\ncategory=Apps\n");
   CHECK(configs_rename("other", "Other Renamed") == CONFIGS_OK);
   CHECK(config_file_read("other", &pf) == CONFIGS_OK);
   CHECK_STR(pf.info.name, "Other Renamed");
   CHECK_STR(pf.info.category, "Apps");
   CHECK_STR(configs_running()->id, "geos");
   CHECK_STR(configs_running()->name, max_name);
   CHECK(configs_rename(CONFIGS_FACTORY_NTSC, "Changed") == CONFIGS_ERROR);
   CHECK(configs_rename(CONFIGS_FACTORY_PAL, "Changed") == CONFIGS_ERROR);
   CHECK(configs_rename("../escape", "Changed") == CONFIGS_ERROR);

   // Main can't be renamed.
   fresh_card();
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_rename_running("Other") == CONFIGS_ERROR);
   CHECK_STR(configs_running()->name, "Default");
}

static void test_delete(void) {
   fresh_card();
   make_config("geos", "name=GEOS\nmachine=C64\n");
   make_config("elite", "name=Elite\nmachine=C64\n");
   write_file("/configs/elite/vice.ini", "[C64]\n");
   write_file("/configs/elite/vice.in~", "[C64]\n");
   write_file("/configs/elite/settings.txt", "palette=1\n");
   // Left by the web UI's editor.
   write_file("/configs/elite/settings.txt.bak", "palette=0\n");
   write_file("/configs/elite/config.txt.bak", "name=Old\nmachine=C64\n");
   write_file("/configs/elite/vice.ini.bak", "[C64]\n");
   write_file("/disks/elite.d64", "disk image");
   write_file("/configs/active.txt", "config=geos\n");
   configs_boot_init("C64/PAL/HDMI");

   // Not Main, not the running config, nothing invalid.
   CHECK(configs_delete("main") == CONFIGS_ERROR);
   CHECK(configs_delete("geos") == CONFIGS_ERROR);
   CHECK(exists("/configs/geos/config.txt"));
   CHECK(configs_delete("../disks") == CONFIGS_ERROR);
   CHECK(configs_delete("") == CONFIGS_ERROR);
   CHECK(configs_delete(NULL) == CONFIGS_ERROR);
   CHECK(configs_delete("gone") == CONFIGS_ERROR);

   // Permanent deletion releases the original id and removes associated data.
   CHECK(configs_delete("elite") == CONFIGS_OK);
   CHECK(!exists("/configs/elite"));
   CHECK(configs_deleted_count()==0);
   CHECK(configs_switch_to("elite")==CONFIGS_ERROR);
   CHECK(exists("/disks/elite.d64"));
   char reused[33];CHECK(configs_create("Elite",reused,sizeof(reused))==CONFIGS_OK);CHECK_STR(reused,"elite");
   make_config("keep","name=Keep\nmachine=C64\n");
   write_file("/configs/keep/my-notes.txt","mine");
   CHECK(configs_delete("keep")==CONFIGS_OK);CHECK(!exists("/configs/keep"));

}

// ---- Autostart ----

static void test_autostart_config(void) {
   fresh_card();
   make_config("elite", "name=Elite\nmachine=C64\ncategory=Games\n");
   write_file("/configs/active.txt", "config=elite\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_autostart(), "");

   // Saved straight away into config.txt; other keys are kept.
   CHECK(configs_set_autostart("SD:/games/elite.d64") == CONFIGS_OK);
   CHECK_STR(configs_autostart(), "SD:/games/elite.d64");
   CHECK_STR(read_file("/configs/elite/config.txt"),
             "name=Elite\ncategory=Games\nmachine=C64\n"
             "autostart=SD:/games/elite.d64\n");

   // Start-up picks it up.
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_autostart(), "SD:/games/elite.d64");

   // A rename made since start-up isn't lost by a later autostart change.
   CHECK(configs_rename_running("Elite Plus") == CONFIGS_OK);
   CHECK(configs_set_autostart("SD:/games/elite2.d64") == CONFIGS_OK);
   ConfigFile pf;
   CHECK(config_file_read("elite", &pf) == CONFIGS_OK);
   CHECK_STR(pf.info.name, "Elite Plus");
   CHECK_STR(pf.autostart, "SD:/games/elite2.d64");

   // Clearing removes the key.
   CHECK(configs_clear_autostart() == CONFIGS_OK);
   CHECK_STR(configs_autostart(), "");
   CHECK(strstr(read_file("/configs/elite/config.txt"), "autostart") == NULL);

   // Clear only the Config selection: leave PRG/disk bytes and both saved
   // Autostart Warp states untouched. All files are temporary host fixtures.
   char warp_settings_path[256];
   configs_new_settings_file("elite", warp_settings_path, sizeof(warp_settings_path));
   const char *media_paths[] = {"/games/elite2.d64", "/games/demo.prg"};
   const char *selected_paths[] = {"SD:/games/elite2.d64", "SD:/games/demo.prg"};
   for (int warp = 0; warp <= 1; warp++) {
      const char *warp_settings = warp ? "AutostartWarp=1\n" : "AutostartWarp=0\n";
      write_file(warp_settings_path, warp_settings);
      for (int media = 0; media < 2; media++) {
         write_file(media_paths[media], "MEDIA BYTES MUST REMAIN UNCHANGED");
         CHECK(configs_set_autostart(selected_paths[media]) == CONFIGS_OK);
         CHECK(configs_clear_autostart() == CONFIGS_OK);
         CHECK_STR(configs_autostart(), "");
         CHECK_STR(read_file(media_paths[media]), "MEDIA BYTES MUST REMAIN UNCHANGED");
         CHECK_STR(read_file(warp_settings_path), warp_settings);
         ConfigFile cleared;
         CHECK(config_file_read("elite", &cleared) == CONFIGS_OK);
         CHECK_STR(cleared.autostart, "");
         CHECK_STR(cleared.info.name, "Elite Plus");
      }
   }

   // An empty or missing path isn't an autostart.
   CHECK(configs_set_autostart("") == CONFIGS_ERROR);
   CHECK(configs_set_autostart(NULL) == CONFIGS_ERROR);
   CHECK_STR(configs_autostart(), "");
}

static void test_startup_disks(void) {
   fresh_card();
   make_config("geos", "name=GEOS\nmachine=C64\n");
   write_file("/configs/active.txt", "config=geos\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_startup_disk(0), "");
   CHECK_STR(configs_startup_disk(-1), "");
   CHECK_STR(configs_startup_disk(CONFIGS_NUM_DRIVES), "");

   // Saved straight away; empty drives are left out.
   const char *disks[CONFIGS_NUM_DRIVES] = {"SD:/disks/geos.d64", "", NULL,
                                             "SD:/disks/data.d81"};
   CHECK(configs_set_startup_disks(disks) == CONFIGS_OK);
   CHECK_STR(configs_startup_disk(0), "SD:/disks/geos.d64");
   CHECK_STR(configs_startup_disk(1), "");
   CHECK_STR(configs_startup_disk(3), "SD:/disks/data.d81");
   CHECK_STR(read_file("/configs/geos/config.txt"),
             "name=GEOS\nmachine=C64\ndisk_8=SD:/disks/geos.d64\n"
             "disk_11=SD:/disks/data.d81\n");

   // Start-up picks them up; the autostart is kept separately.
   CHECK(configs_set_autostart("SD:/disks/geos.d64") == CONFIGS_OK);
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_startup_disk(0), "SD:/disks/geos.d64");
   CHECK_STR(configs_startup_disk(3), "SD:/disks/data.d81");
   CHECK_STR(configs_autostart(), "SD:/disks/geos.d64");

   // Setting again replaces all four drives.
   const char *one[CONFIGS_NUM_DRIVES] = {NULL, "SD:/disks/b.d64", NULL, NULL};
   CHECK(configs_set_startup_disks(one) == CONFIGS_OK);
   CHECK_STR(configs_startup_disk(0), "");
   CHECK_STR(configs_startup_disk(1), "SD:/disks/b.d64");

   // Clearing removes them and keeps the autostart.
   CHECK(configs_clear_startup_disks() == CONFIGS_OK);
   CHECK_STR(configs_startup_disk(1), "");
   CHECK_STR(read_file("/configs/geos/config.txt"),
             "name=GEOS\nmachine=C64\nautostart=SD:/disks/geos.d64\n");

   // A path too long to keep isn't saved cut short.
   char long_path[CONFIGS_MAX_PATH_LEN + 10];
   memset(long_path, 'a', sizeof(long_path) - 1);
   long_path[sizeof(long_path) - 1] = '\0';
   const char *too_long[CONFIGS_NUM_DRIVES] = {long_path, NULL, NULL, NULL};
   CHECK(configs_set_startup_disks(too_long) == CONFIGS_ERROR);
   CHECK_STR(configs_startup_disk(0), "");

   // Main's persisted startup assignments are immutable.
   fresh_card();configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_set_startup_disks(disks)==CONFIGS_ERROR);
   CHECK(!exists("/configs/main/c64.txt"));
}

static void test_autostart_main(void) {
   fresh_card();configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_set_autostart("SD:/x.prg")==CONFIGS_ERROR);
   CHECK(configs_clear_autostart()==CONFIGS_ERROR);
   CHECK(!exists("/configs/main/c64.txt"));
   // Existing legacy Main selections still load without being rewritten.
   write_file("/configs/main/c64.txt","autostart=SD:/geos/GEOS64.D81\n");
   write_file("/configs/active.txt","config=_factory-ntsc\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_autostart(),"");
   CHECK(configs_clear_autostart()==CONFIGS_ERROR);
   CHECK_STR(read_file("/configs/main/c64.txt"),"autostart=SD:/geos/GEOS64.D81\n");
   write_file("/configs/main/vic20.txt","autostart=SD:/vic/game.prg\n");
   configs_boot_init("VIC20/PAL/HDMI");
   CHECK_STR(configs_autostart(),"");
   CHECK(configs_set_autostart("SD:/other.prg")==CONFIGS_ERROR);
}

// ---- Machines ----

static void test_machine_switching(void) {
   fresh_card();
   make_config("elite", "name=Elite\nmachine=C64/PAL/HDMI\n");
   make_config("vic", "name=PAL 16K\nmachine=VIC20/PAL/HDMI\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_machine_for(CONFIGS_FACTORY_NTSC), configs_factory_info(0)->machine);
   CHECK_STR(configs_machine_for("main"), "");
   CHECK(configs_switch_to("main") == CONFIGS_ERROR);
   // Start once on another machine: the power-on config's machine is put
   // back for the next power-on, and once is kept for BMC64's own restarts.
   write_file("/configs/active.txt", "config=elite\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK(configs_start_once("vic") == CONFIGS_OK);
   CHECK_ACTIVE( "config=elite\nonce=vic\n");
   configs_boot_init("VIC20/PAL/HDMI");
   CHECK_STR(configs_running()->id, "vic");
   CHECK_STR(configs_return_machine(), "C64/PAL/HDMI");
   configs_after_boot();
   CHECK_ACTIVE( "config=elite\n");
   configs_before_reboot();
   CHECK_ACTIVE( "config=elite\nonce=vic\n");
   make_config("hd", "name=HD\nmachine=C64/PAL/HDMI\n");
   write_file("/configs/active.txt", "config=hd\n");
   configs_boot_init("C64/PAL/HDMI");
   // In a config, same machine: the config follows the standard and output.
   write_file("/configs/active.txt", "config=hd\n");
   configs_machine_switched("C64/NTSC/HDMI/VICE 720p@60Hz");
   CHECK_ACTIVE( "config=hd\n");
   CHECK_STR(read_file("/configs/hd/config.txt"),
             "name=HD\nmachine=C64/NTSC/HDMI\n");
   // Another machine: the config follows too, and Main isn't changed.
   write_file("/configs/active.txt",
              "config=hd\n");
   write_file("/configs/hd/settings-c64.txt", "c64 settings\n");
   configs_machine_switched("VIC20/PAL/HDMI/VICE 720p@50Hz");
   CHECK_ACTIVE(
             "config=hd\n");
   CHECK_STR(read_file("/configs/hd/config.txt"),
             "name=HD\nmachine=VIC20/PAL/HDMI\n");
   // It starts on the VIC-20 with the VIC-20's own (new) settings file; the
   // C64's are kept for when it goes back.
   configs_boot_init("VIC20/PAL/HDMI");
   CHECK_STR(configs_running()->id, "hd");
   CHECK_STR(configs_settings_file(),
             "/configs/hd/settings-vic20.txt");
   CHECK_STR(read_file("/configs/hd/settings-c64.txt"), "c64 settings\n");
   // A config that can't be read: Main.
   write_file("/configs/active.txt", "config=gone\n");
   configs_machine_switched("VIC20/PAL/HDMI/VICE 720p@50Hz");
   CHECK_ACTIVE(
             "config=_factory-ntsc\n");

   // A full header in machine= works too.
   make_config("full", "name=Full\nmachine=C64/PAL/HDMI/VICE 720p@50Hz\n");
   write_file("/configs/active.txt", "config=full\n");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_running()->id, "full");

   char desc[64];
   configs_machine_desc("C64 / PAL / HDMI / VICE 720p@50Hz", desc, sizeof(desc));
   CHECK_STR(desc, "C64/PAL/HDMI");
   configs_machine_desc("C64", desc, sizeof(desc));
   CHECK_STR(desc, "C64");
}

static void test_settings_files(void) {
   // New configs get the running machine's settings file.
   fresh_card();
   configs_boot_init("Plus4Emu/PAL/HDMI");
   char path[CONFIGS_MAX_PATH_LEN];
   configs_new_settings_file("ted", path, sizeof(path));
   CHECK_STR(path, "/configs/ted/settings-plus4emu.txt");

   // An older config's settings.txt is read at boot, without being renamed
   // or rewritten at boot.
   make_config("old", "name=Old\nmachine=C128/PAL/HDMI\n");
   write_file("/configs/old/settings.txt", "c128 settings\n");
   write_file("/configs/active.txt", "config=old\n");
   configs_boot_init("C128/PAL/HDMI");
   CHECK_STR(configs_settings_file(),
             "/configs/old/settings.txt");
   CHECK(exists("/configs/old/settings.txt"));
   configs_after_boot();
   CHECK_STR(configs_settings_file(),
             "/configs/old/settings.txt");
   CHECK(!exists("/configs/old/settings-c128.txt"));
   CHECK_STR(read_file("/configs/old/settings.txt"), "c128 settings\n");
   configs_boot_init("C128/PAL/HDMI");
   CHECK_STR(configs_settings_file(),
             "/configs/old/settings.txt");

   // An explicit machine switch records legacy ownership in metadata;
   // its original settings file is never renamed or read by the new machine.
   make_config("move", "name=Move\nmachine=C64/PAL/HDMI\n");
   write_file("/configs/move/settings.txt", "c64 settings\n");
   write_file("/configs/active.txt", "config=move\n");
   configs_boot_init("C64/PAL/HDMI");
   configs_machine_switched("Plus4/PAL/HDMI/VICE 720p@50Hz");
   CHECK(exists("/configs/move/settings.txt"));
   CHECK(!exists("/configs/move/settings-c64.txt"));
   CHECK_STR(read_file("/configs/move/settings.txt"), "c64 settings\n");
   configs_boot_init("Plus4/PAL/HDMI");
   CHECK_STR(configs_settings_file(),
             "/configs/move/settings-plus4.txt");

   // Returning to its original machine reads the unchanged legacy file.
   configs_machine_switched("C64/PAL/HDMI");
   configs_boot_init("C64/PAL/HDMI");
   CHECK_STR(configs_settings_file(), "/configs/move/settings.txt");
   CHECK_STR(read_file("/configs/move/settings.txt"), "c64 settings\n");

   // Persistent boot references remain protected after machine fallback.
   configs_boot_init("Plus4/PAL/HDMI");
   write_file("/configs/move/settings-c64.txt", "x\n");
   write_file("/configs/move/settings-c64.txt.bak", "x\n");
   CHECK(configs_delete("move") == CONFIGS_ERROR);
   CHECK(configs_switch_to(CONFIGS_FACTORY_NTSC) == CONFIGS_OK);
   CHECK(configs_delete("move") == CONFIGS_OK);
   CHECK(!exists("/configs/move"));
   CHECK(configs_deleted_count()==0);
}

static void check_label(const char *machine, const char *expected) {
   char label[16];
   configs_machine_label(machine, label, sizeof(label));
   CHECK_STR(label, expected);
}

static void test_machines(void) {
   check_label("C64/PAL/HDMI/VICE 720p@50Hz", "C64");
   check_label("C128/NTSC/HDMI/VICE 720p@60Hz", "C128");
   check_label("VIC20/PAL/HDMI/VICE 720p@50Hz", "VIC20");
   check_label("Plus4/PAL/HDMI/VICE 720p@50Hz", "Plus4");
   check_label("Plus4Emu/PAL/HDMI/720p@50Hz", "Plus4Emu");
   check_label("Pet/NTSC/HDMI/VICE 720p@60Hz", "Pet");
   check_label("vic20", "vic20");
   check_label("C64", "C64");
   check_label("", "");
   check_label(NULL, "");
   char small[4];
   configs_machine_label("VIC20/PAL", small, sizeof(small));
   CHECK_STR(small, "VIC");

   CHECK(configs_machine_matches("C64/PAL/HDMI/VICE 720p@50Hz", "C64"));
   CHECK(configs_machine_matches("C64", "C64"));
   CHECK(configs_machine_matches("c64", "C64"));
   CHECK(configs_machine_matches("Plus4Emu/PAL", "Plus4Emu"));
   CHECK(!configs_machine_matches("Plus4/PAL", "Plus4Emu"));
   CHECK(!configs_machine_matches("C128/NTSC", "C64"));
   CHECK(!configs_machine_matches("C64", "C128"));
   CHECK(!configs_machine_matches("", "C64"));
   CHECK(!configs_machine_matches("/PAL", "C64"));
   CHECK(!configs_machine_matches("C64", ""));
   CHECK(!configs_machine_matches(NULL, "C64"));
   CHECK(configs_machine_matches("C64/PAL/HDMI", "c64 / pal / hdmi / VICE 720p@50Hz"));
   CHECK(!configs_machine_matches("C64/PAL/HDMI/VICE 1080p@50Hz",
                                   "C64/PAL/HDMI/VICE 720p@50Hz"));

   CHECK(configs_machine_covers("C64/PAL", "C64/PAL/HDMI/VICE 720p@50Hz"));
   CHECK(configs_machine_covers("C64/PAL/HDMI/VICE 720p@50Hz",
                                 "C64/PAL/HDMI/VICE 720p@50Hz"));
   CHECK(!configs_machine_covers("C64/PAL/HDMI", "C64/PAL"));
   CHECK(!configs_machine_covers("C64/NTSC", "C64/PAL/HDMI/VICE 720p@50Hz"));
   CHECK(!configs_machine_covers("", "C64"));
   CHECK(!configs_machine_covers("C64", ""));
   // The description may hold '/'.
   CHECK(configs_machine_covers("C64/PAL/DPI/Gert 666/RGB",
                                 "C64/PAL/DPI/Gert 666/RGB"));
}

int main(void) {
   char root[] = "/tmp/bmc64-configs-test-XXXXXX";
   if (mkdtemp(root) == NULL) {
      perror("mkdtemp");
      return 1;
   }
   snprintf(card_root, sizeof(card_root), "%s", root);
   setenv("SD_TEST_ROOT", root, 1);

   test_kv_parse();
   test_kv_append();
   test_config_parse();
   test_config_format();
   test_active_parse();
   test_ids();
   test_no_configs();
   test_boot_config();
   test_start_once();
   test_switch_to();
   test_safe_mode();
   test_list();
   test_create();
   test_rename();
   test_delete();
   test_autostart_config();
   test_autostart_main();
   test_startup_disks();
   test_machines();
   test_machine_switching();
   test_settings_files();

   remove_tree(root);

   if (failures) {
      fprintf(stderr, "configs tests: %d failure(s)\n", failures);
      return 1;
   }
   printf("configs tests passed\n");
   return 0;
}
