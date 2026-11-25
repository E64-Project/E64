#ifndef NETWORK_TIME_SYNC_H
#define NETWORK_TIME_SYNC_H

class CNetSubSystem;
struct BmcNetworkConfig;

bool ConfigureSystemTimeZone(int offset_minutes);
void StartNetworkTimeSync(CNetSubSystem *network, const BmcNetworkConfig &config);

#endif
