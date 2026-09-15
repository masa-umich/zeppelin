/*
 * Network time synchronization.
 *
 * Updates the system clock from a network time server (SNTP). Provides a
 * one-shot sync as well as a dedicated thread that periodically re-syncs.
 */

#pragma once

#include <zephyr/kernel.h>

// Perform a single, blocking synchronization of the system clock from the
// network time server. Intended to be called once the network is up.
// Returns 0 on success or a negative errno on failure.
int time_sync_now(void);

// Spawn the dedicated thread that periodically synchronizes the system clock
// from the network time server. The thread performs an initial sync and then
// re-syncs at a fixed interval.
// Returns the thread id of the spawned sync thread.
k_tid_t time_sync_start(void);
