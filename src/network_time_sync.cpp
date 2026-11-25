#include "network_time_sync.h"
#include "network_config.h"

#include <circle/logger.h>
#include <circle/net/dnsclient.h>
#include <circle/net/netsubsystem.h>
#include <circle/net/ntpclient.h>
#include <circle/sched/scheduler.h>
#include <circle/timer.h>

#include <reent.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

bool ConfigureSystemTimeZone(int offset_minutes) {
  int absolute_offset = offset_minutes;
  if (absolute_offset < 0) {
    absolute_offset = -absolute_offset;
  }

  char timezone[16];
  snprintf(timezone, sizeof(timezone), "UTC%c%d:%02d",
           offset_minutes > 0 ? '-' : '+', absolute_offset / 60,
           absolute_offset % 60);

  if (_setenv_r(_REENT, "TZ", timezone, 1) != 0) {
    return false;
  }

  _tzset_r(_REENT);

  return CTimer::Get()->SetTimeZone(offset_minutes);
}

namespace {

// Gregorian weekday: Sunday=0, including dates outside the host libc range.
int Weekday(int year, int month, int day) {
  static const int offsets[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  if (month < 3) --year;
  return (year + year / 4 - year / 100 + year / 400 + offsets[month - 1] + day) % 7;
}

// Days from 1970-01-01 (UTC); used only for US DST transition dates.
int64_t DaysFromCivil(int year, unsigned month, unsigned day) {
  year -= month <= 2;
  const int era = (year >= 0 ? year : year - 399) / 400;
  const unsigned yoe = unsigned(year - era * 400);
  const unsigned doy = (153 * (month > 2 ? month - 3 : month + 9) + 2) / 5 + day - 1;
  const unsigned yoe_days = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return int64_t(era) * 146097 + yoe_days - 719468;
}

int EffectiveOffset(unsigned utc_seconds, const BmcNetworkConfig &config) {
  if (!config.dst_enabled) return config.timezone_minutes;
  time_t instant = static_cast<time_t>(utc_seconds);
  struct tm *utc = gmtime(&instant);
  if (!utc) return config.timezone_minutes;
  const int year = utc->tm_year + 1900;
  const int march_second_sunday = 1 + (7 - Weekday(year, 3, 1)) % 7 + 7;
  const int november_first_sunday = 1 + (7 - Weekday(year, 11, 1)) % 7;
  // Transition at 02:00 local standard in March, daylight in November.
  const int64_t start = DaysFromCivil(year, 3, march_second_sunday) * 86400
      + (2 * 60 - config.timezone_minutes) * 60;
  const int64_t end = DaysFromCivil(year, 11, november_first_sunday) * 86400
      + (2 * 60 - config.timezone_minutes - 60) * 60;
  return utc_seconds >= start && utc_seconds < end
       ? config.timezone_minutes + 60 : config.timezone_minutes;
}

class NetworkTimeSyncTask : public CTask {
public:
  NetworkTimeSyncTask(CNetSubSystem *network, const BmcNetworkConfig &config)
      : mNetwork(network), mConfig(config) {
    SetName("ntpwait");
  }

  void Run(void) override {
    // Wait for the network to become operational.
    while (!mNetwork->IsRunning()) {
      CScheduler::Get()->Sleep(1);
    }

    for (;;) {

      CIPAddress server;
      CDNSClient resolver(mNetwork);
      if (!resolver.Resolve(mConfig.ntp_server, &server)) {
        CLogger::Get()->Write("ntp", LogWarning,
                              "Cannot resolve NTP server: %s", mConfig.ntp_server);
        CScheduler::Get()->Sleep(300);
        continue;
      }

      CNTPClient client(mNetwork);
      unsigned timestamp = client.GetTime(server);

      if (timestamp == 0) {
        CLogger::Get()->Write(
            "ntp",
            LogWarning,
            "Cannot get time from NTP server: %s", mConfig.ntp_server
        );

        CScheduler::Get()->Sleep(300);
        continue;
      }

      if (CTimer::Get()->SetTime(timestamp, FALSE)) {
        ConfigureSystemTimeZone(EffectiveOffset(timestamp, mConfig));
        CLogger::Get()->Write(
            "ntp",
            LogNotice,
            "System time set from NTP: %u UTC",
            timestamp
        );
      } else {
        CLogger::Get()->Write(
            "ntp",
            LogWarning,
            "Cannot set system time from NTP"
        );
      }

      // Resynchronize every 15 minutes.
      CScheduler::Get()->Sleep(900);
    }
  }

private:
  CNetSubSystem *mNetwork;
  BmcNetworkConfig mConfig;
};

}  // namespace

void StartNetworkTimeSync(CNetSubSystem *network, const BmcNetworkConfig &config) {
  new NetworkTimeSyncTask(network, config);
}
