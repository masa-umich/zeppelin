#include <helium/opcua/server.h>
#include <open62541/plugin/eventloop.h>
#include <zephyr/kernel.h>

/* Supply the EventLoop's monotonic clock in OPC UA's 100 ns units. */
static UA_DateTime monotonic_time(UA_EventLoop* event_loop) {
    return (UA_DateTime)(k_ticks_to_ns_floor64(k_uptime_ticks()) / 100);
}
