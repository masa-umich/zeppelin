#include <helium/net_init.h>

#if !defined(CONFIG_NET_CONNECTION_MANAGER)
    #error "CONFIG_NET_CONNECTION_MANAGER must be enabled for net_init to work"
#endif

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/conn_mgr_connectivity.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/net_if.h>

LOG_MODULE_REGISTER(net_init, LOG_LEVEL_INF);

// Semaphores and callback storage must outlive the registered network events.
K_SEM_DEFINE(network_connected, 0, 1);
K_SEM_DEFINE(network_disconnected, 0, 1);
static struct net_mgmt_event_callback l4_cb;

// Event handler for Layer 4 (IP connectivity) events
static void l4_event_handler(struct net_mgmt_event_callback* cb, uint64_t event,
                             struct net_if* iface) {
    switch (event) {
        case NET_EVENT_L4_CONNECTED:
            LOG_INF("Network L4 Connected!");
            k_sem_give(&network_connected);
            break;
        case NET_EVENT_L4_DISCONNECTED:
            LOG_INF("Network L4 Disconnected!");
            k_sem_give(&network_disconnected);
            break;
        case NET_EVENT_IPV4_ADDR_ADD:
            LOG_INF("Got an IP");
            break;
        default:
            break;
    }
}

int net_init(int timeout) {
    LOG_INF("Initialzing network");

    int err;
    struct net_if* iface = net_if_get_default();

    if (iface == NULL) {
        LOG_ERR("No default network interface found");
        return -ENODEV;
    }

    net_mgmt_init_event_callback(&l4_cb, l4_event_handler,
                                 NET_EVENT_L4_CONNECTED | NET_EVENT_L4_DISCONNECTED);
    net_mgmt_add_event_callback(&l4_cb);

    // Check if the network interface even needs to be bound for something like WiFi vs
    // Ethernet
    if (conn_mgr_if_is_bound(iface)) {
        // Attempt to connect (non-blocking)
        // This is generic but will go to a connection manager
        // implementation depending on the target's available interfaces
        err = conn_mgr_if_connect(iface);
        if (err != 0 && err != -EALREADY) return err;
    }

    // Wait until we actually connect
    err = k_sem_take(&network_connected, K_MSEC(timeout));
    if (err == 0) {
        LOG_INF("Done initializing network");
    } else if (err == -EBUSY) {
        LOG_ERR("Error initializing network connection");
        return err;
    } else if (err == -EAGAIN) {
        LOG_ERR("Timed out waiting for network connection");
        return err;
    } else {
        LOG_ERR("dafuq?");
        return err;
    }
    return 0;
}
