/*
 * All initialization
 */

#include "init.h"

#include <helium/time.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/conn_mgr_connectivity.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/net_if.h>

// Network timeout in milliseconds, for no timeout do K_FOREVER
#define NETWORK_TIMEOUT_VAL 30000

LOG_MODULE_REGISTER(init, LOG_LEVEL_INF);

// Semaphores and callback storage must outlive the registered network events.
K_SEM_DEFINE(network_connected, 0, 1);
K_SEM_DEFINE(network_disconnected, 0, 1);
static struct net_mgmt_event_callback l4_cb;

// Pull the led0 specification from the devicetree overlay
const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(DT_ALIAS(button0), gpios);

// Button callback data and handler
static struct gpio_callback button_cb_data;
void button_pressed_handler(const struct device* port, struct gpio_callback* cb,
                            gpio_port_pins_t pins) {
    printk("Button Pressed!\n");
}

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

// Init GPIO
int gpio_init(void) {
    LOG_INF("Initializing GPIO");
    if (!gpio_is_ready_dt(&led) || !gpio_is_ready_dt(&button)) return -1;

    int err;
    err = gpio_pin_configure_dt(&led, GPIO_OUTPUT_ACTIVE);
    if (err != 0) return err;
    err = gpio_pin_configure_dt(&button, GPIO_INPUT);
    if (err != 0) return err;

    // Configure the button interrupt
    gpio_pin_interrupt_configure_dt(&button, GPIO_INT_EDGE_TO_ACTIVE);
    gpio_init_callback(&button_cb_data, button_pressed_handler, BIT(button.pin));
    gpio_add_callback_dt(&button, &button_cb_data);
    LOG_INF("Done initializng GPIO");
    return 0;
}

int net_init(void) {
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
    err = k_sem_take(&network_connected, K_MSEC(NETWORK_TIMEOUT_VAL));
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

int time_init(void) {
    LOG_INF("Initializing system time");
    if (!time_sync_now()) {
        LOG_INF("Done initializing system time");
    } else {
        LOG_WRN("Continuing without synchronized system time");
    }
    return 0;
}

// Initialize all GPIO, start networking, sync system time, etc
int init(void) {
    int err;

    // Init GPIO
    err = gpio_init();
    if (err != 0) return err;

    // Init network
    err = net_init();
    if (err != 0) return err;

    // Init time
    err = time_init();
    if (err != 0) return err;

    // Done!
    LOG_INF("All initialization finished!");
    return 0;
}
