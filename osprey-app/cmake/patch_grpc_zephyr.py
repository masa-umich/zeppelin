#!/usr/bin/env python3
"""Apply the small POSIX platform declaration needed by gRPC 1.51 on Zephyr."""

from __future__ import annotations

import argparse
from pathlib import Path


ZEPHYR_PLATFORM = '''#elif defined(__ZEPHYR__) || defined(GPR_ZEPHYR)
#define GPR_PLATFORM_STRING "zephyr"
#define GPR_ZEPHYR 1
#define GPR_CPU_POSIX 1
#define GPR_GCC_ATOMIC 1
#define GPR_ARCH_32 1
#define GPR_POSIX_ENV 1
#define GPR_POSIX_LOG 1
#define GPR_POSIX_STRING 1
#define GPR_POSIX_SYNC 1
#define GPR_POSIX_TIME 1
#define GPR_HAS_PTHREAD_H 1
#define GPR_GETPID_IN_UNISTD_H 1
#define GRPC_ARES 0
#define GRPC_POSIX_SOCKET 1
#define GRPC_POSIX_NO_SPECIAL_WAKEUP_FD 1
#define GRPC_TIMER_USE_GENERIC 1
'''

ZEPHYR_IOMGR_PLATFORM = '''#elif defined(GPR_ZEPHYR)
/* Zephyr POSIX sockets support poll(), but not Linux epoll/ifaddrs. */
#define GRPC_POSIX_SOCKET 1
#define GRPC_POSIX_NO_SPECIAL_WAKEUP_FD 1
#define GRPC_POSIX_SOCKETUTILS 1
#define GRPC_TIMER_USE_GENERIC 1
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grpc_source", type=Path)
    parser.add_argument("zlib_source", type=Path, nargs="?")
    args = parser.parse_args()
    header = args.grpc_source / "include/grpc/impl/codegen/port_platform.h"
    source = header.read_text(encoding="utf-8")
    marker = "#else\n#error \"Could not auto-detect platform\""
    if "#define GPR_PLATFORM_STRING \"zephyr\"" not in source:
        if marker not in source:
            raise SystemExit(f"could not find gRPC platform insertion point in {header}")
        source = source.replace(marker, ZEPHYR_PLATFORM + marker, 1)
        header.write_text(source, encoding="utf-8")

    iomgr_header = args.grpc_source / "src/core/lib/iomgr/port.h"
    iomgr = iomgr_header.read_text(encoding="utf-8")
    iomgr_marker = "#elif !defined(GPR_NO_AUTODETECT_PLATFORM)\n#error \"Platform not recognized\""
    if "/* Zephyr POSIX sockets support poll()" not in iomgr:
        if iomgr_marker not in iomgr:
            raise SystemExit(f"could not find gRPC I/O manager platform insertion point in {iomgr_header}")
        iomgr = iomgr.replace(iomgr_marker, ZEPHYR_IOMGR_PLATFORM + iomgr_marker, 1)
    iomgr = iomgr.replace("not Linux epoll/eventfd/ifaddrs", "not Linux epoll/ifaddrs")

    # The generic GRPC_POSIX_SOCKET bundle enables Linux epoll and eventfd.
    # Keep the common POSIX socket features but select poll as Zephyr's actual
    # event mechanism. This uses upstream gRPC poll/socket implementations.
    feature_block = '''#ifdef GRPC_POSIX_SOCKET
#define GRPC_POSIX_SOCKET_ARES_EV_DRIVER 1
#define GRPC_POSIX_SOCKET_EV 1
#define GRPC_POSIX_SOCKET_EV_POLL 1
#define GRPC_POSIX_SOCKET_EV_EPOLL1 1
#define GRPC_POSIX_SOCKET_IF_NAMETOINDEX 1
#define GRPC_POSIX_SOCKET_IOMGR 1
#define GRPC_POSIX_SOCKET_RESOLVE_ADDRESS 1
#define GRPC_POSIX_SOCKET_SOCKADDR 1
#define GRPC_POSIX_SOCKET_SOCKET_FACTORY 1
#define GRPC_POSIX_SOCKET_TCP 1
#define GRPC_POSIX_SOCKET_TCP_CLIENT 1
#define GRPC_POSIX_SOCKET_TCP_SERVER 1
#define GRPC_POSIX_SOCKET_TCP_SERVER_UTILS_COMMON 1
#define GRPC_POSIX_SOCKET_UDP_SERVER 1
#define GRPC_POSIX_SOCKET_UTILS_COMMON 1
#endif
'''
    zephyr_features = '''#ifdef GRPC_POSIX_SOCKET
#define GRPC_POSIX_SOCKET_EV 1
#define GRPC_POSIX_SOCKET_EV_POLL 1
#define GRPC_POSIX_SOCKET_IOMGR 1
#define GRPC_POSIX_SOCKET_RESOLVE_ADDRESS 1
#define GRPC_POSIX_SOCKET_SOCKADDR 1
#define GRPC_POSIX_SOCKET_SOCKET_FACTORY 1
#define GRPC_POSIX_SOCKET_TCP 1
#define GRPC_POSIX_SOCKET_TCP_CLIENT 1
#define GRPC_POSIX_SOCKET_TCP_SERVER 1
#define GRPC_POSIX_SOCKET_TCP_SERVER_UTILS_COMMON 1
#define GRPC_POSIX_SOCKET_UDP_SERVER 1
#define GRPC_POSIX_SOCKET_UTILS_COMMON 1
#endif
'''
    if "#if !defined(GPR_ZEPHYR)\n#ifdef GRPC_POSIX_SOCKET" not in iomgr:
        if feature_block not in iomgr:
            raise SystemExit(f"could not find gRPC POSIX feature bundle in {iomgr_header}")
        iomgr = iomgr.replace(feature_block, "#if !defined(GPR_ZEPHYR)\n" + feature_block + "#else\n" + zephyr_features + "#endif\n", 1)
    iomgr_header.write_text(iomgr, encoding="utf-8")

    if args.zlib_source is not None:
        # zlib's generated zconf.h defines the historical FAR macro. Zephyr's
        # unistd.h pulls the STM32 device header, which has a register member
        # also named FAR. Include the kernel first so that SoC header is
        # parsed before zlib introduces that macro.
        for template_name in ("zconf.h.cmakein", "zconf.h.in"):
            template = args.zlib_source / template_name
            text = template.read_text(encoding="utf-8")
            marker = "#define ZCONF_H\n"
            zephyr_include = "#if defined(__ZEPHYR__)\n#include <zephyr/kernel.h>\n#endif\n"
            if zephyr_include not in text:
                if marker not in text:
                    raise SystemExit(f"could not find zlib config insertion point in {template}")
                text = text.replace(marker, marker + zephyr_include, 1)
                template.write_text(text, encoding="utf-8")

    # ARM's default enum ABI chooses a byte for grpc_status_code. Abseil's
    # integer parser requires 32/64 bits, as gRPC expects on desktop targets.
    # Preserve all wire status values and the existing -1 sentinel while
    # forcing this public type to have a signed 32-bit representation.
    status_header = args.grpc_source / "include/grpc/impl/codegen/status.h"
    status = status_header.read_text(encoding="utf-8")
    sentinel = "  GRPC_STATUS__DO_NOT_USE = -1"
    if "GRPC_STATUS__FORCE_32_BIT" not in status:
        if sentinel not in status:
            raise SystemExit(f"could not find gRPC status enum in {status_header}")
        status = status.replace(
            sentinel, sentinel + ",\n  GRPC_STATUS__FORCE_32_BIT = 0x7fffffff", 1
        )
        status_header.write_text(status, encoding="utf-8")

    # Zephyr's libc does not expose _SC_NPROCESSORS_CONF. Use its architecture
    # APIs so gRPC gets the configured CPU count and current CPU identity.
    cpu_source = args.grpc_source / "src/core/lib/gpr/cpu_posix.cc"
    cpu_text = cpu_source.read_text(encoding="utf-8")
    zephyr_include = "#if defined(GPR_ZEPHYR)\n#include <zephyr/kernel.h>\n#endif\n"
    include_marker = "#include <grpc/support/port_platform.h>\n"
    if zephyr_include not in cpu_text:
        if include_marker not in cpu_text:
            raise SystemExit(f"could not find gRPC CPU source include point in {cpu_source}")
        cpu_text = cpu_text.replace(include_marker, include_marker + zephyr_include, 1)
    cpu_probe = "  ncpus = sysconf(_SC_NPROCESSORS_CONF);"
    cpu_zephyr_probe = (
        "#if defined(GPR_ZEPHYR)\n  ncpus = arch_num_cpus();\n#else\n"
        + cpu_probe
        + "\n#endif"
    )
    if cpu_zephyr_probe not in cpu_text:
        if cpu_probe not in cpu_text:
            raise SystemExit(f"could not find gRPC CPU count probe in {cpu_source}")
        cpu_text = cpu_text.replace(cpu_probe, cpu_zephyr_probe, 1)
    current_cpu = "  return (unsigned)grpc_core::HashPointer(thread_id, gpr_cpu_num_cores());"
    zephyr_current_cpu = "  return (unsigned)arch_curr_cpu()->id;"
    if zephyr_current_cpu not in cpu_text:
        if current_cpu not in cpu_text:
            raise SystemExit(f"could not find gRPC current CPU implementation in {cpu_source}")
        cpu_text = cpu_text.replace(
            current_cpu,
            "#if defined(GPR_ZEPHYR)\n"
            + zephyr_current_cpu
            + "\n#else\n"
            + current_cpu
            + "\n#endif",
            1,
        )
    cpu_source.write_text(cpu_text, encoding="utf-8")

    cmake = args.grpc_source / "CMakeLists.txt"
    cmake_source = cmake.read_text(encoding="utf-8")
    guard = "# Only fetch external proto archives when code generation is enabled."
    if guard not in cmake_source:
        start = "# Setup external proto library at third_party/envoy-api with 2 download URLs\n"
        end = "\nif(WIN32)\n  set(_gRPC_BASELIB_LIBRARIES ws2_32 crypt32)\nendif()"
        if start not in cmake_source or end not in cmake_source:
            raise SystemExit(f"could not find gRPC optional archive block in {cmake}")
        cmake_source = cmake_source.replace(
            start,
            f"if(gRPC_BUILD_CODEGEN)\n{guard}\n" + start,
            1,
        )
        cmake_source = cmake_source.replace(
            end,
            "\nendif()\n" + end,
            1,
        )
        cmake.write_text(cmake_source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
