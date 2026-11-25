#ifndef E64_GPIO_RECOVERY_H
#define E64_GPIO_RECOVERY_H
#ifdef __cplusplus
extern "C" {
#endif
/* Backend starts with all matrix lines and joystick selectors input-pull-up.
 * row(pa,1) drives LOW; row(pa,0) restores input-pull-up. No events. */
typedef struct {
 void *context;
 void (*row)(void *, unsigned pa, int low);
 int (*read)(void *, unsigned pb);
 void (*delay_us)(void *, unsigned us);
 unsigned (*time_us)(void *);
} GpioRecoveryIO;
/* 0 normal, 1 NTSC. Shift has no recovery function. Bounded 50ms window; every row is restored. */
int gpio_recovery_sample(const GpioRecoveryIO *io);
#ifdef __cplusplus
}
#endif
#endif
