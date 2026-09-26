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
gRPC C++ client, and generated service stubs. It constructs the complete Synnax
client and attempts authentication:

```sh
bash osprey-app/cmake/fetch-dependencies.sh \
  .cache/synnax-deps .cache/synnax-deps/dependencies.cmake --full
.venv/bin/west build -b nucleo_h723zg osprey-app \
  --build-dir osprey-app/build-full -p always -- \
  -DOSPREY_SYNNAX_FULL_CLIENT=ON
```

This is an experimental port, not a validated network application. `main.cpp`
sets the server address; `full-client.conf` sets the board's static IPv4 address.
Review the credentials and port in `synnax::Config` before connecting.

TLS is unsupported. Only `grpc++_unsecure` and `grpc_unsecure` are linked;
OpenSSL and BoringSSL are absent. Selecting `secure=true` throws an explicit
error rather than downgrading to plaintext.

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

The Zephyr SDK ships a single-thread C++ runtime and no ARM 64-bit atomic
library. `port/` supplies the pthread-backed gthread and C++ thread ABI,
thread-safe static initialization, and per-thread exception bookkeeping.
`src/atomic64.cpp` supplies actual atomic operations protected by a Zephyr
spinlock. Patches also resolve 32-bit type aliases, STM32 macro collisions,
console terminal detection, and libc differences.

The transport port uses Zephyr's pollable eventfd and real POSIX sockets,
plus kernel-heap-backed Abseil allocation. It does not provide Linux epoll,
POSIX pipes, TLS, or an MMU/mmap emulation. The heap and thread limits are fixed;
successful linking alone does not establish sufficient runtime memory for gRPC.
