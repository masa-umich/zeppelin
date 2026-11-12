#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include "led.h"

static const struct pwm_dt_spec red_led = PWM_DT_SPEC_GET(DT_ALIAS(red_led));
static const struct pwm_dt_spec green_led = PWM_DT_SPEC_GET(DT_ALIAS(green_led));
static const struct pwm_dt_spec blue_led = PWM_DT_SPEC_GET(DT_ALIAS(blue_led));

static const struct device *const uart_dev = DEVICE_DT_GET(DT_NODELABEL(uart8));

static void print_uart(const char *buf)
{
    for (int i = 0; buf[i] != '\0'; i++) {
        uart_poll_out(uart_dev, buf[i]);
    }
}

int main(void)
{
	led_set_brightness(&green_led, 20);
	led_set_brightness(&red_led, 40);

	unsigned char rx_char;

	if (!device_is_ready(uart_dev)) {
        return 0;
    }

	print_uart("Zephyr UART Polling Echo Ready. Type something:\r\n");

    while (true) {
        /* uart_poll_in() returns 0 when a byte is read, or -1 if empty */
        if (uart_poll_in(uart_dev, &rx_char) == 0) {
            /* Echo the received character back */
            uart_poll_out(uart_dev, rx_char);

            /* Add a line feed if Enter (carriage return) is pressed */
            if (rx_char == '\r') {
                uart_poll_out(uart_dev, '\n');
            }
        } else {
            /* Yield briefly when idle to prevent starving lower-priority threads */
            k_msleep(1);
        }
    }
}