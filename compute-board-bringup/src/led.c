#include "led.h"

#include <stdint.h>

int led_set_brightness(const struct pwm_dt_spec *led, unsigned int percent)
{
    if (percent > 100U) {
        return 0;
    }

    if (!pwm_is_ready_dt(led)) {
        return 0;
    }

    uint32_t pulse = (uint64_t)led->period * percent / 100U;
    return pwm_set_pulse_dt(led, pulse);
}