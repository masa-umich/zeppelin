/*
 * All initialization
 */

#pragma once

extern const struct gpio_dt_spec led;

// Initialize all GPIO, start networking, sync system time, etc
int init(void);
