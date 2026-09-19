#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/net/hostname.h>

#include "init.h"

#define SLEEP_TIME_MS 1000

int main(void) {
    int ret = init();
    if (ret != 0) {
        printk("Init failed :(");
        return ret;
    }

    const char* name = net_hostname_get();
    printk("Current device hostname: %s\n", name);

    while (1) {
        gpio_pin_toggle_dt(&led);  // led is an extern
        printk("LED Toggled\n");
        k_msleep(SLEEP_TIME_MS);
    }

    return 0;
}
