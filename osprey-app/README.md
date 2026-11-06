# Osprey

Reference OPC UA firmware for other MASA boards, tested with Zephyr 4.5.0,
open62541 1.5.10, and the NUCLEO-H723ZG.

## Simulation

This project has simulation support, though since it's built for GPIO interaction you can only really verify networking parts. Run the sim with:
```bash
just sim run osprey-app
```

Then in Synnax you'll want to target `opc.tcp://127.0.0.1:4840` (the default `localhost` doesn't work for some reason). 

## Build and connect

Complete the [workspace setup](../README.md#setup), then run from the repository root:

```sh
just build osprey-app
just flash osprey-app
```

Connect Ethernet and use `opc.tcp://169.254.0.50:4840`. The host needs an address
on `169.254.0.0/16`; automatic link-local addressing usually supplies one. If the
host routes this subnet through another adapter, select the Ethernet interface.

Boolean nodes are `ns=1;s=led.green`, `ns=1;s=led.yellow`, `ns=1;s=led.red`
(read/write), and `ns=1;s=button.toggle` (read-only). Each debounced USER press
toggles the button value; holding it does not repeat. Send value-only writes,
without source timestamps. Subscriptions are disabled, so clients should poll.

## Application configuration

Use [prj.conf](prj.conf) as the starting point:

- **Networking/platform APIs:** TCP sockets, entropy, libc/POSIX support, eventfd,
  and logging required by the open62541 Zephyr backend.
- **Memory and connection capacity:** stack, kernel heap, poll slots, and socket
  contexts needed by the server; see below.
- **IP configuration:** static address, subnet, and gateway for the deployment.
- **OPC UA features:** a minimal namespace and disabled unused features, following
  upstream's Zephyr example. Other library options retain their defaults.

## Connection count

For `N` clients, each using one SecureChannel and Session, update these together:

| Setting | Required capacity | Current value |
| --- | --- | --- |
| `config.maxSecureChannels`, `config.maxSessions` in [server.c](src/server.c) | `N` each | `6` |
| `CONFIG_ZVFS_POLL_MAX` | `N + 2`: clients, listener, wakeup eventfd | `8` |
| `CONFIG_NET_MAX_CONTEXTS` | At least `N + 1`; use `N + 2` for reconnect headroom | `8` |
| `CONFIG_NET_MAX_CONN` | At least `N + 1` | `8` (Zephyr default here) |

These counts assume one listening socket. Include existing drivers and test tools
in the client count. Insufficient poll capacity stalls connection processing.

## Minimum memory configuration

The tested explicit memory requirements are:

```conf
CONFIG_MAIN_STACK_SIZE=4096
CONFIG_HEAP_MEM_POOL_SIZE=1024
```

The default 1 KiB main stack is too small for server startup. Socket address lookup
uses `k_calloc()`, requiring a nonzero kernel heap. open62541 allocations use the
**separate libc heap**, whose default arena takes the remaining RAM.

This board needs no custom RAM layout or packet/buffer-pool overrides. The server
uses 8 KiB transport buffers and an 8 KiB message limit. Recheck memory requirements
when changing features, message sizes, or client load.

## Reusing the build integration

Copy the relevant blocks from [CMakeLists.txt](CMakeLists.txt):

1. Fetch the pinned open62541 archive with its SHA-256 and `SOURCE_SUBDIR arch/zephyr`.
   Register its `arch` directory in `EXTRA_ZEPHYR_MODULES` **before**
   `find_package(Zephyr)` so Zephyr discovers its Kconfig options. Link the app
   against `open62541` afterward. Keep default datatype generation; restricting
   it can omit types still referenced by 1.5.10.
2. Keep the guarded socket-type replacement. open62541 1.5.10 incorrectly declares
   `typedef struct zsock_fd_set UA_fd_set;`; Zephyr already defines `zsock_fd_set`
   as a typedef. The replacement implements
   [upstream fix 938fcc5](https://github.com/open62541/open62541/commit/938fcc53866d1e7d572b07a3bfe6c9f134240262).
   Remove it only after verifying the pinned release includes that fix.
3. For `CONFIG_NATIVE_LIBC`, keep the `eventfd`/`eventfd_write` remapping to
   `zvfs_eventfd`/`zvfs_eventfd_write`; host descriptors cannot be polled by Zephyr.
   For `CONFIG_NET_SOCKETS_OFFLOAD`, keep the added Zephyr `getnameinfo.c` source,
   which supplies a function otherwise omitted by that build.

Set the new board target and provide GPIO aliases `led0`, `led1`, `led2`, and `sw0`
if reusing this LED/button example. Native simulation also needs those aliases
and suitable simulated GPIOs; the generic networking overlay alone is insufficient.

## Time source workaround

The 1.5.10 Zephyr backend returns milliseconds where OPC UA expects 100 ns units,
making timers run 10,000 times too slowly. Supply the EventLoop clock before
`UA_Server_newWithConfig()`, as in [server.c](src/server.c):

```c
static UA_DateTime monotonic_time(UA_EventLoop* event_loop) {
    return (UA_DateTime)(k_ticks_to_ns_floor64(k_uptime_ticks()) / 100);
}

/* After configuring the server: */
config.eventLoop->dateTime_nowMonotonic = monotonic_time;
```

Include `<open62541/plugin/eventloop.h>` and `<zephyr/kernel.h>`. This keeps button
sampling and protocol timers correct without modifying the library's clock source.
