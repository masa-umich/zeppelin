#include <helium/time.h>
#include <time.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/sntp.h>
#include <zephyr/net/socket.h>
#include <zephyr/sys/clock.h>

LOG_MODULE_REGISTER(time_sync, LOG_LEVEL_INF);

// Network time server used for synchronization.
#define TIME_SYNC_SERVER "pool.ntp.org"

// Timeout for a single SNTP query, in milliseconds.
#define TIME_SYNC_QUERY_TIMEOUT_MS 4000

// Right after L4 connect, DNS servers (from DHCP or router advertisements)
// may not be installed yet and NTP pool servers can time out, so retry a few
// times before giving up.
#define TIME_SYNC_ATTEMPTS 10
#define TIME_SYNC_RETRY_DELAY_MS 2000

// Interval between periodic re-syncs performed by the sync thread.
#define TIME_SYNC_INTERVAL_MS (60 * 60 * 1000)  // 1 hour

#define TIME_SYNC_STACK_SIZE 2048
#define TIME_SYNC_THREAD_PRIORITY 5

// Static storage for the dedicated time sync thread
static K_THREAD_STACK_DEFINE(time_sync_stack, TIME_SYNC_STACK_SIZE);
static struct k_thread time_sync_thread;

// Resolve the time server pinned to IPv4 and run one SNTP query against it.
static int sntp_query_ipv4(struct sntp_time* sntp_time) {
    struct zsock_addrinfo hints = {
        .ai_family = AF_INET,
        .ai_socktype = SOCK_DGRAM,
    };
    struct zsock_addrinfo* addr = NULL;

    int ret = zsock_getaddrinfo(TIME_SYNC_SERVER, "123", &hints, &addr);
    if (ret != 0) {
        return ret < 0 ? ret : -ret;
    }

    ret = sntp_simple_addr(addr->ai_addr, addr->ai_addrlen, TIME_SYNC_QUERY_TIMEOUT_MS,
                           sntp_time);
    zsock_freeaddrinfo(addr);
    return ret;
}

int time_sync_now(void) {
    struct sntp_time sntp_time;
    int ret;

    for (int attempt = 1;; attempt++) {
        ret = sntp_query_ipv4(&sntp_time);
        if (ret == 0) break;

        if (attempt >= TIME_SYNC_ATTEMPTS) {
            LOG_ERR("Failed to query time server \"%s\": %d (%d attempts)",
                    TIME_SYNC_SERVER, ret, attempt);
            return ret;
        }

        LOG_WRN("Time server query failed (%d), retrying...", ret);
        k_msleep(TIME_SYNC_RETRY_DELAY_MS);
    }

    struct timespec tspec = {
        .tv_sec = (time_t)sntp_time.seconds,
        .tv_nsec = 0,
    };

    ret = sys_clock_settime(SYS_CLOCK_REALTIME, &tspec);
    if (ret < 0) {
        LOG_ERR("Failed to set system clock: %d", ret);
        return ret;
    }

    LOG_INF("System clock synchronized (epoch %llu)",
            (unsigned long long)sntp_time.seconds);
    return 0;
}

// Thread entry point: sync immediately, then re-sync on a fixed interval
static void time_sync_thread_entry(void* arg1, void* arg2, void* arg3) {
    ARG_UNUSED(arg1);
    ARG_UNUSED(arg2);
    ARG_UNUSED(arg3);

    while (1) {
        (void)time_sync_now();
        k_msleep(TIME_SYNC_INTERVAL_MS);
    }
}

// Spawn the dedicated time sync thread
k_tid_t time_sync_start(void) {
    return k_thread_create(&time_sync_thread, time_sync_stack,
                           K_THREAD_STACK_SIZEOF(time_sync_stack),
                           time_sync_thread_entry, NULL, NULL, NULL,
                           TIME_SYNC_THREAD_PRIORITY, 0, K_NO_WAIT);
}
