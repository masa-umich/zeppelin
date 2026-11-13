/*
 * Network initialization for the Helium app
 * Must have Connection Manager enabled in project settings
 */

#pragma once

#if !defined(CONFIG_NET_CONNECTION_MANAGER)
#error "CONFIG_NET_CONNECTION_MANAGER must be enabled for net_init to work"
#endif

int net_init(int timeout);
