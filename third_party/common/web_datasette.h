#ifndef WEB_DATASETTE_H
#define WEB_DATASETTE_H
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
  int supported, attached, writable, counter, mode, motor, pending, error;
  unsigned serial;
  char filename[1024];
} WebDatasette;
/* Emulator thread bridge; no filesystem work in the HTTP task. */
void emux_web_datasette_read(WebDatasette *state);
int emux_web_datasette_command(int command, const char *expected);
void web_datasette_tick(void);
void web_datasette_status(WebDatasette *state);
int web_datasette_queue(int command);
int web_datasette_attach(const char *path, unsigned *serial);
#ifdef __cplusplus
}
#endif
#endif
