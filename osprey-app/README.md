# Osprey Synnax bring-up

Osprey is a C++20 application using the actual upstream
`client/cpp/synnax.h` umbrella header. The OPC UA server and open62541 build
have been removed.

The default application is deliberately a header and protobuf smoke test:
it serializes and parses a real Synnax login request on a POSIX-created C++
thread, then prints its result. It does not construct `synnax::Synnax` or open
a network connection. All client implementation files except `transport.cpp`
are compiled into a static archive; the linker discards unused APIs.

## Build the smoke application

From the repository root, with the Zephyr workspace and SDK installed:

```sh
.venv/bin/west build -b nucleo_h723zg osprey-app \
  --build-dir osprey-app/build -p always
```

The build downloads immutable source archives, verifies SHA-256 hashes, builds
a native `protoc`, generates Synnax's messages, and cross-compiles the libraries.
It needs a native C/C++ compiler, CMake, Ninja, Python, Git, and network access on
the first build. The Boost archive is large; allow several gigabytes of disk space.

For a reusable dependency cache or an offline build after downloading:

```sh
bash osprey-app/cmake/fetch-dependencies.sh \
  .cache/synnax-deps .cache/synnax-deps/dependencies.cmake
```

CMake automatically loads that generated configuration when present. To keep
build caches inside this checkout, prefix the build with
`CCACHE_DIR="$PWD/.cache/ccache"` and append
`-- -DUSER_CACHE_DIR="$PWD/.cache/zephyr"`.

Generated firmware is under `osprey-app/build/zephyr/`. Flash with
`.venv/bin/west flash --build-dir osprey-app/build`.

## Plaintext transport experiment

The optional transport configuration builds the real upstream `transport.cpp`,
gRPC C++ client, and generated service stubs. The login-only application includes
the same master header, constructs Synnax's authentication middleware and
plaintext gRPC login transport, and attempts authentication:

```sh
bash osprey-app/cmake/fetch-dependencies.sh \
  .cache/synnax-deps .cache/synnax-deps/dependencies.cmake --full
.venv/bin/west build -b nucleo_h723zg osprey-app \
  --build-dir osprey-app/build-full -p always -- \
  -DOSPREY_SYNNAX_AUTH_ONLY=ON \
  -DOSPREY_SYNNAX_FULL_CLIENT=OFF \
  -DOSPREY_SYNNAX_DTCM_HEAP=ON
```

This is an experimental port, not a validated network application. `main.cpp`
sets the server address; `full-client.conf` sets the board's static IPv4 address.
Review the credentials and port in `synnax::Config` before connecting.

TLS is unsupported. Only `grpc++_unsecure` and `grpc_unsecure` are linked;
OpenSSL and BoringSSL are absent. Selecting `secure=true` throws an explicit
error rather than downgrading to plaintext.

The login-only build fits the STM32H723. Constructing the complete
`synnax::Synnax` object eagerly initializes every client API and still exceeds
the board's flash capacity. To reproduce that experiment, select
`-DOSPREY_SYNNAX_FULL_CLIENT=ON -DOSPREY_SYNNAX_AUTH_ONLY=OFF` instead.
These options are mutually exclusive. The default smoke build selects neither.

Measured with Zephyr SDK 1.0.1 on `nucleo_h723zg`, whose internal flash is 1 MiB:

| Application | Flash | Result |
| --- | ---: | --- |
| Master header and protobuf smoke test | 84,616 bytes | Links |
| Real plaintext login client | 792,588 bytes | Links |
| Complete Synnax constructor | 1,569,236 bytes | Exceeds flash by 520,660 bytes |

The login build reserves 134,708 bytes of main RAM, all 128 KiB of DTCM for
malloc, and the board's 16 KiB SRAM2 reservation. These are linker allocations;
peak runtime usage and a successful server login have not been tested on
hardware.

## Dependencies and platform changes

| Dependency | Pin |
| --- | --- |
| Synnax client 0.58.1 | `37e28149a4dba24c191e6bc7f45bf6a6fb49c5d2` |
| protobuf / native protoc | 21.12 (protoc 3.21.12) |
| Abseil | 20250127.1 |
| nlohmann/json | 3.12.0 |
| Boost headers | 1.88.0 |
| gRPC (transport only) | 1.51.3 |
| RE2 (transport only) | 2022-12-01 |
| zlib (transport only) | 1.2.13 |

The Synnax snapshot is current upstream source at the time of this port.
The older protobuf and gRPC pins reduce dependency and platform requirements;
they differ from Synnax's current Bazel dependency versions. Client/server
compatibility still needs testing against the intended Synnax server.

`OSPREY_SYNNAX_LITE_PROTO=ON` generates Synnax-owned messages without reflection
or descriptor registration. Set it to `OFF` for full message generation.
The full protobuf library remains available for Google's well-known types and
Synnax's JSON conversion code. Static archives and section garbage collection
retain only code reachable from the application. `prj.conf` selects `-Oz`.
Transport builds also enable link-time optimization. All firmware uses
release-mode settings. `OSPREY_SYNNAX_STRIP_LOGS=ON` removes Abseil's stream
logging and formatted CHECK messages; failing checks still abort, and raw
fatal diagnostics remain available. Turn this option off for richer logs.

`OSPREY_SYNNAX_MINIMAL_GRPC=ON` keeps HTTP/2, plaintext TCP, native DNS,
pick-first connection selection, authentication, deadlines, and resource
quotas. It removes optional load balancers, proxies, fault injection, and
tracing, and fixes experimental switches at their release defaults. The
EventEngine scheduler remains; its alternate socket implementation is
unsupported, while gRPC uses its existing POSIX TCP transport.

`OSPREY_SYNNAX_CLIENT_ONLY_STUBS=ON` omits generated RPC server declarations
and implementations. Client stubs, including streaming and asynchronous
methods, remain available. Set it to `OFF` to generate the server API too.
The Synnax constructor and UUID stream operator are moved into separate archive
members on Zephyr, preserving their behavior while keeping unused references
from retaining additional runtime code before LTO.

`OSPREY_SYNNAX_GRPC_NO_EXCEPTIONS=ON` removes exception cleanup inside gRPC
to reduce flash. Synnax and the application still support exceptions. An
allocation failure inside gRPC cannot safely unwind to the application and
is fatal. Set this option to `OFF` to retain gRPC's cleanup code.

On the STM32H723, `OSPREY_SYNNAX_DTCM_HEAP=ON` moves the 128 KiB libc malloc
arena to the board's actual DTCM region. The kernel heap and Ethernet buffers
remain in SRAM. The relocation survives LTO and does not change advertised
memory sizes. DTCM is CPU-only: do not pass these malloc buffers directly to
DMA. The full arena uses all available DTCM.

The Zephyr SDK ships a single-thread C++ runtime and no ARM 64-bit atomic
library. `port/` supplies the pthread-backed gthread and C++ thread ABI,
thread-safe static initialization, and per-thread exception bookkeeping.
With SDK 1.0.1, size optimization also selects a `space/libstdc++.a` variant
that fails the throw/catch tests and reports exception counts as zero.
`port/runtime.cmake` selects the regular GNU C++ runtime through a symlink in
the build directory while retaining `-Oz` compilation. It leaves the SDK,
libc, and libgcc unchanged.
`src/atomic64.cpp` supplies actual atomic operations protected by a Zephyr
spinlock. Patches also resolve 32-bit type aliases, STM32 macro collisions,
console terminal detection, and libc differences.

The transport port uses Zephyr's pollable eventfd and real POSIX sockets,
plus kernel-heap-backed Abseil allocation. It does not provide Linux epoll,
POSIX pipes, TLS, or an MMU/mmap emulation. The heap and thread limits are fixed;
successful linking alone does not establish sufficient runtime memory for gRPC.
Abseil time conversion supports UTC and fixed offsets. Named timezone files
are unavailable on this target.

## Reproduce the runtime checks

The standalone runtime test checks concurrent once/static initialization,
exception retry, condition-variable notification, per-thread exception state,
TLS destructor order, and contended 64-bit atomics. The Abseil test checks
allocator reclamation, mutex contention, a condition-variable wait, UTC and
fixed-offset conversion, and rejection of unavailable named timezones.
Both pass on Cortex-M3 QEMU. The runtime tests also pass with `-Oz` and LTO.

```sh
.venv/bin/west build -b qemu_cortex_m3 osprey-app/tests/runtime \
  --build-dir osprey-app/build-runtime -p always
.venv/bin/west build -t run --build-dir osprey-app/build-runtime
.venv/bin/west build -b qemu_cortex_m3 osprey-app/tests/runtime \
  --build-dir osprey-app/build-runtime-lto -p always -- \
  -DEXTRA_CONF_FILE=lto.conf
.venv/bin/west build -t run --build-dir osprey-app/build-runtime-lto
.venv/bin/west build -b qemu_cortex_m3 osprey-app/tests/abseil \
  --build-dir osprey-app/build-abseil -p always
.venv/bin/west build -t run --build-dir osprey-app/build-abseil
```

The success markers are `runtime-port: PASS`,
`ABSL_PORT_TEST allocator=1 sync=1`, and
`ABSL_TIME_TEST utc=1 offset=1 unsupported_zone=1`.
Use Ctrl-A, then X to exit QEMU.
