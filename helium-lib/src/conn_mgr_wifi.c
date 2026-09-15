/*
 * Application-defined connectivity backend for the generic WIFI_MGMT
 * connection manager binding.
 */

#include <zephyr/kernel.h>

// Don't include for targets without WiFi
#if defined(CONFIG_NET_CONNECTION_MANAGER_CONNECTIVITY_WIFI_MGMT)

#include <zephyr/logging/log.h>
#include <zephyr/net/conn_mgr/connectivity_wifi_mgmt.h>
#include <zephyr/net/conn_mgr_connectivity_impl.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/wifi_mgmt.h>

LOG_MODULE_REGISTER(conn_mgr_wifi, LOG_LEVEL_INF);

// Start association. Must be non-blocking: net_mgmt requests to the WiFi L2
// kick off the connection and the driver raises WiFi/L4 events on completion.
static int wifi_mgmt_connect(struct conn_mgr_conn_binding* const binding) {
    struct net_if* iface = binding->iface;

#if defined(CONFIG_WIFI_CREDENTIALS_CONNECT_STORED)
    // Connect using credentials stored via the wifi_credentials library
    // Possible future task: allow multiple connection options
    int ret = net_mgmt(NET_REQUEST_WIFI_CONNECT_STORED, iface, NULL, 0);

    if (ret) {
        LOG_ERR("Failed to request connect with stored credentials: %d", ret);
    }
    return ret;
#else
    LOG_ERR(
        "No connect method available: enable CONFIG_WIFI_CREDENTIALS_CONNECT_STORED "
        "or provide explicit connect parameters");
    ARG_UNUSED(iface);
    return -ENOTSUP;
#endif
}

// Tear down the association / cancel any in-progress connection attempt
static int wifi_mgmt_disconnect(struct conn_mgr_conn_binding* const binding) {
    struct net_if* iface = binding->iface;
    int ret = net_mgmt(NET_REQUEST_WIFI_DISCONNECT, iface, NULL, 0);

    if (ret) {
        LOG_ERR("Failed to request disconnect: %d", ret);
    }
    return ret;
}

// WiFi init - we don't really have to do anything here at the moment
static void wifi_mgmt_init(struct conn_mgr_conn_binding* const binding) {
    ARG_UNUSED(binding);
}

static struct conn_mgr_conn_api conn_api = {
    .connect = wifi_mgmt_connect,
    .disconnect = wifi_mgmt_disconnect,
    .init = wifi_mgmt_init,
};

CONN_MGR_CONN_DEFINE(CONNECTIVITY_WIFI_MGMT, &conn_api);

#endif /* CONFIG_NET_CONNECTION_MANAGER_CONNECTIVITY_WIFI_MGMT */
