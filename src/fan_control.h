#ifndef E64_FAN_CONTROL_H
#define E64_FAN_CONTROL_H
#ifdef __cplusplus
extern "C" {
#endif
#define FAN_GPIO 11
#define FAN_MIN_C 30
#define FAN_MAX_C 80
#define FAN_PREFS_FILE "/system/fan-prefs.txt"
/* Keep the existing on-disk values for Off and automatic control. */
enum { FAN_OFF = 0, FAN_AUTO = 1, FAN_ON = 2 };
typedef struct { int enabled, on_c, off_c; } FanSettings;
typedef struct { FanSettings settings; int available, output, pending, error; } FanStatus;
int fan_settings_valid(const FanSettings *p);
int fan_decide(const FanSettings *p, int available, int was_on, int millic);
int fan_prefs_load(FanSettings *p);
int fan_prefs_save(const FanSettings *p);
/* Core 0 only: pin reservation, startup and periodic mailbox/storage service. */
int fan_dpi_allowed(void); /* target policy; shared common library has no target macro */
void fan_gpio_init(int dpi);
void fan_start(void);
void fan_service(void);
/* Thread-safe snapshots and one outstanding request. Saving is deferred to
 * core 0; error/pending report completion without blocking the emulator. */
void fan_get_status(FanStatus *status);
int fan_request(const FanSettings *settings);
/* Native staged edits: compare committed snapshot under the request lock. */
int fan_request_if_current(const FanSettings *settings, const FanSettings *expected);
void fan_prepare_shutdown(void);
#ifdef __cplusplus
}
#endif
#endif
