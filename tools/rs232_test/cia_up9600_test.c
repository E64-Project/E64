/* CCGMS UP9600 CIA1 rapid-write regression.
 * Uses production ciacore.c and ciatimer.c.
 */
#include <assert.h>
#include <stdlib.h>
#include "alarm.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "cia.h"
#include "ciatimer.h"

static alarm_context_t alarms;
static CLOCK cpu_clock;
static int rmw_flag;
static uint8_t output[8];
static unsigned output_count;

static void serial_output(cia_context_t *cia, uint8_t value)
{
    (void)cia;
    if (output_count < sizeof(output))
        output[output_count++] = value;
}

static void interrupt_output(cia_context_t *cia, int level, CLOCK clock)
{
    (void)cia;
    (void)level;
    (void)clock;
}


void alarm_log_too_many_alarms(void)
{
    fputs("Too many CIA test alarms\\n", stderr);
    abort();
}

void alarm_unset(alarm_t *alarm)
{
    alarm_context_t *ctx = alarm->context;
    int idx = alarm->pending_idx;

    if (idx < 0)
        return;

    unsigned last = --ctx->num_pending_alarms;

    if ((unsigned)idx != last) {
        ctx->pending_alarms[idx] = ctx->pending_alarms[last];
        ctx->pending_alarms[idx].alarm->pending_idx = idx;
    }

    alarm->pending_idx = -1;
    alarm_context_update_next_pending(ctx);
}

int main(void)
{
    cia_context_t cia;
    ciat_t timer_a, timer_b;
    alarm_t alarm_a = {0}, alarm_b = {0};

    memset(&cia, 0, sizeof(cia));
    memset(&timer_a, 0, sizeof(timer_a));
    memset(&timer_b, 0, sizeof(timer_b));

    alarms.next_pending_alarm_clk = (CLOCK)~0L;
    alarm_a.context = &alarms;
    alarm_b.context = &alarms;
    alarm_a.pending_idx = -1;
    alarm_b.pending_idx = -1;

    cia.ta_alarm = &alarm_a;
    cia.tb_alarm = &alarm_b;
    cia.clk_ptr = &cpu_clock;
    cia.rmw_flag = &rmw_flag;
    cia.ta = &timer_a;
    cia.tb = &timer_b;
    cia.store_sdr = serial_output;
    cia.cia_set_int_clk = interrupt_output;

    ciat_init_table();
    ciat_init(&timer_a, "CIA1 Timer A", cpu_clock, &alarm_a);
    ciat_init(&timer_b, "CIA1 Timer B", cpu_clock, &alarm_b);

    /* NTSC UP9600: Timer A period approximately 53 cycles. */
    ciacore_store(&cia, CIA_TAL, 53);
    ciacore_store(&cia, CIA_TAH, 0);
    ciacore_store(&cia, CIA_CRA, 0x41);

    /* Two fragments written before one timer period expires. */
    cpu_clock = 1;
    ciacore_store(&cia, CIA_SDR, 0x12);

    cpu_clock = 19;
    ciacore_store(&cia, CIA_SDR, 0x34);

    /* Advance the actual CIA timer implementation. */
    cpu_clock = 2500;
    (void)ciacore_read(&cia, CIA_CRA);

    fflush(stdout);
    printf("CIA1 fragments delivered: %u\n", output_count);
    for (unsigned i = 0; i < output_count; ++i)
        printf("  fragment %u: $%02X\n", i + 1, output[i]);

    assert(output_count == 2);
    assert(output[0] == 0x12);
    assert(output[1] == 0x34);

    puts("PASS: Both UP9600 serial fragments preserved");
    return 0;
}
