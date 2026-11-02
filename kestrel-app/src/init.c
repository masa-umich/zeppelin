/*
 * All initialization
 */

#include "init.h"

#include <helium/time.h>
#include <helium/net_init.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Network timeout in milliseconds, for no timeout do K_FOREVER
#define NETWORK_TIMEOUT_VAL 30000

LOG_MODULE_REGISTER(init, LOG_LEVEL_INF);

// Pull the led0 specification from the devicetree overlay
const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(DT_ALIAS(button0), gpios);

// Button callback data and handler
static struct gpio_callback button_cb_data;
void button_pressed_handler(const struct device* port, struct gpio_callback* cb,
                            gpio_port_pins_t pins) {
    printk("Button Pressed!\n");
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
    err = net_init(NETWORK_TIMEOUT_VAL);
    if (err != 0) return err;

    // Init time
    err = time_init();
    if (err != 0) return err;

    // Done!
    LOG_INF("All initialization finished!");
    return 0;
}
