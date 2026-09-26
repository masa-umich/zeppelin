#!/usr/bin/env python3
"""Use Zephyr's real eventfd implementation for gRPC poll wakeups."""

import argparse
from pathlib import Path


def replace(path: Path, before: str, after: str) -> None:
    text = path.read_text()
    if after in text:
        return
    if before not in text:
        raise SystemExit(f"gRPC socket patch insertion point missing in {path}")
    path.write_text(text.replace(before, after, 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grpc_source", type=Path)
    source = parser.parse_args().grpc_source

    # Recent Abseil headers no longer provide StrCat transitively.
    replace(source / "src/core/lib/iomgr/tcp_posix.cc",
            '#include <grpc/support/port_platform.h>\n',
            '#include <grpc/support/port_platform.h>\n#include "absl/strings/str_cat.h"\n')

    replace(source / "src/core/lib/iomgr/ev_posix.cc",
            "#include <string.h>\n", "#include <string.h>\n"
            "#if defined(GPR_ZEPHYR)\n#include <errno.h>\n#include <limits.h>\n#endif\n")
    replace(source / "src/core/lib/iomgr/ev_posix.cc",
            "#ifndef GPR_AIX\ngrpc_poll_function_type grpc_poll_function = poll;\n",
            "#if defined(GPR_ZEPHYR)\n"
            "static int zephyr_poll(struct pollfd *fds, nfds_t nfds, int timeout) {\n"
            "  if (nfds > INT_MAX) { errno = EINVAL; return -1; }\n"
            "  return poll(fds, static_cast<int>(nfds), timeout);\n"
            "}\n"
            "grpc_poll_function_type grpc_poll_function = zephyr_poll;\n"
            "#elif !defined(GPR_AIX)\ngrpc_poll_function_type grpc_poll_function = poll;\n")

    # Despite gRPC's historical macro name, eventfd is also implemented by
    # Zephyr and is pollable. No Linux epoll or pipe backend is enabled.
    replace(
        source / "src/core/lib/iomgr/port.h",
        "#elif defined(GPR_ZEPHYR)\n",
        "#elif defined(GPR_ZEPHYR)\n"
        "#define GRPC_POSIX_WAKEUP_FD 1\n"
        "#define GRPC_LINUX_EVENTFD 1\n",
    )
    for header in ["src/core/lib/iomgr/port.h", "include/grpc/impl/codegen/port_platform.h"]:
        path = source / header
        text = path.read_text()
        start = text.index("#elif defined(GPR_ZEPHYR)" if header.startswith("src/")
                           else "#elif defined(__ZEPHYR__)")
        end = text.index("#elif" if header.startswith("src/") else "#else", start + 6)
        block = text[start:end].replace("#define GRPC_POSIX_NO_SPECIAL_WAKEUP_FD 1\n", "")
        path.write_text(text[:start] + block + text[end:])

    for relative in ["src/core/lib/iomgr/wakeup_fd_eventfd.cc",
                     "src/core/lib/event_engine/posix_engine/wakeup_fd_eventfd.cc"]:
        replace(source / relative, "#include <sys/eventfd.h>\n",
                "#include <sys/eventfd.h>\n"
                "#if defined(GPR_ZEPHYR)\n"
                "// Zephyr has no exec; close-on-exec is unnecessary.\n"
                "#define EFD_CLOEXEC 0\n"
                "#endif\n")

    # Zephyr has eventfd but no POSIX pipe. Do not compile or reference the
    # optional pipe fallback. Eventfd exhaustion is an actual backend failure.
    replace(source / "src/core/lib/iomgr/wakeup_fd_pipe.cc",
            "#ifdef GRPC_POSIX_WAKEUP_FD\n",
            "#if defined(GRPC_POSIX_WAKEUP_FD) && !defined(GPR_ZEPHYR)\n")
    # The newer EventEngine file already has explicit unsupported-method
    # implementations in its #else branch. Select those for the absent pipe.
    path = source / "src/core/lib/event_engine/posix_engine/wakeup_fd_pipe.cc"
    text = path.read_text()
    text = text.replace("#ifdef GRPC_POSIX_WAKEUP_FD\n",
                        "#if defined(GRPC_POSIX_WAKEUP_FD) && !defined(GPR_ZEPHYR)\n")
    path.write_text(text)
    wakeup = source / "src/core/lib/iomgr/wakeup_fd_posix.cc"
    replace(wakeup,
            "    } else if (grpc_allow_pipe_wakeup_fd &&\n"
            "               grpc_pipe_wakeup_fd_vtable.check_availability()) {\n"
            "      wakeup_fd_vtable = &grpc_pipe_wakeup_fd_vtable;\n",
            "#if !defined(GPR_ZEPHYR)\n"
            "    } else if (grpc_allow_pipe_wakeup_fd &&\n"
            "               grpc_pipe_wakeup_fd_vtable.check_availability()) {\n"
            "      wakeup_fd_vtable = &grpc_pipe_wakeup_fd_vtable;\n"
            "#endif\n")

    for relative in ["src/core/lib/iomgr/socket_utils_posix.cc",
                     "src/core/lib/event_engine/posix_engine/tcp_socket_utils.cc"]:
        replace(source / relative,
                "    if (cloexec) {\n"
                "      flags = fcntl(fd, F_GETFD, 0);\n"
                "      if (flags < 0) goto close_and_error;\n"
                "      if (fcntl(fd, F_SETFD, flags | FD_CLOEXEC) != 0) goto close_and_error;\n"
                "    }\n",
                "#if !defined(GPR_ZEPHYR)  // Zephyr cannot exec another process.\n"
                "    if (cloexec) {\n"
                "      flags = fcntl(fd, F_GETFD, 0);\n"
                "      if (flags < 0) goto close_and_error;\n"
                "      if (fcntl(fd, F_SETFD, flags | FD_CLOEXEC) != 0) goto close_and_error;\n"
                "    }\n"
                "#endif\n")
    for relative, signature in [
        ("src/core/lib/iomgr/socket_utils_common_posix.cc",
         "grpc_error_handle grpc_set_socket_cloexec(int fd, int close_on_exec) {\n"),
        ("src/core/lib/event_engine/posix_engine/tcp_socket_utils.cc",
         "absl::Status PosixSocketWrapper::SetSocketCloexec(int close_on_exec) {\n"),
    ]:
        path = source / relative
        text = path.read_text()
        start = text.index(signature) + len(signature)
        end = text.index("\n}\n", start)
        body = text[start:end]
        if "Zephyr cannot exec" not in body:
            body = ("#if defined(GPR_ZEPHYR)\n"
                    "  // Zephyr cannot exec: there is no child process to inherit the fd.\n"
                    "  return absl::OkStatus();\n"
                    "#else\n" + body + "\n#endif")
            path.write_text(text[:start] + body + text[end:])


if __name__ == "__main__":
    main()
