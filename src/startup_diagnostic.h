#ifndef E64_STARTUP_DIAGNOSTIC_H
#define E64_STARTUP_DIAGNOSTIC_H
/* Temporary Phase 1 instrumentation: set to 0 and rebuild all touched objects
 * to remove diagnostics, or restore build/phase1-diagnostic-originals. */
#define E64_PHASE1_DIAGNOSTIC 1
#if E64_PHASE1_DIAGNOSTIC && (defined(__arm__) || defined(E64_DIAG_HOST_TEST))
#ifdef __cplusplus
extern "C" {
#endif
void e64_diag(int stage, const char *format, ...);
void e64_diag_video(void);
void e64_diag_first_frame(void);
#ifdef __cplusplus
}
#endif
#else
#define e64_diag(...) ((void)0)
#define e64_diag_video() ((void)0)
#define e64_diag_first_frame() ((void)0)
#endif
#endif
