#ifndef COMPUTE_BOARD_BRINGUP_LED_H
#define COMPUTE_BOARD_BRINGUP_LED_H

#include <zephyr/drivers/pwm.h>

int led_set_brightness(const struct pwm_dt_spec* led, unsigned int percent);

#endif