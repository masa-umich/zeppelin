#!/usr/bin/env python3
"""Omit EventEngine's unused POSIX socket path for the Zephyr minimal client."""

from __future__ import annotations

import argparse
from pathlib import Path

from patch_io import write_text_if_changed


GUARD = (
    "#if defined(GRPC_POSIX_SOCKET_TCP) && \\\n    !(defined(GPR_ZEPHYR) && defined(GRPC_MINIMAL_CLIENT))"
)
MARKER = "OSPREY: omit EventEngine POSIX socket machinery"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected one {label}, found {count}")
    return source.replace(old, new, 1)


def patch_header(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return
    guard = f"{GUARD}  // {MARKER}"
    source = source.replace("#ifdef GRPC_POSIX_SOCKET_TCP\n", guard + "\n")
    source = source.replace(
        '#include "src/core/lib/event_engine/posix_engine/event_poller.h"\n',
        f"{guard}\n"
        '#include "src/core/lib/event_engine/posix_engine/event_poller.h"\n'
        "#endif  // EventEngine POSIX socket machinery\n",
    )
    source = source.replace(
        "#endif  // GRPC_POSIX_SOCKET_TCP",
        "#endif  // EventEngine POSIX socket machinery",
    )
    source = source.replace(
        "#else   // GRPC_POSIX_SOCKET_TCP",
        "#else   // EventEngine POSIX socket machinery",
    )
    if source.count(MARKER) != 7:
        raise SystemExit(
            "unexpected pinned posix_engine.h socket guard layout "
            f"({source.count(MARKER)} guarded blocks)"
        )
    write_text_if_changed(path, source, encoding="utf-8")


def patch_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return

    guard = f"{GUARD}  // {MARKER}"
    socket_if = "#ifdef GRPC_POSIX_SOCKET_TCP\n"
    count = source.count(socket_if)
    if count != 5:
        raise SystemExit(f"expected five pinned source socket guards, found {count}")
    source = source.replace(socket_if, guard + "\n")
    source = source.replace(
        "#endif  // GRPC_POSIX_SOCKET_TCP",
        "#endif  // EventEngine POSIX socket machinery",
    )

    # The upstream default constructor is inside the socket implementation
    # block. Supply its scheduler-only equivalent only when that block is out.
    source = replace_once(
        source,
        "#endif  // EventEngine POSIX socket machinery\n\n"
        "struct PosixEventEngine::ClosureData final",
        "#endif  // EventEngine POSIX socket machinery\n"
        "#if defined(GPR_ZEPHYR) && defined(GRPC_MINIMAL_CLIENT)\n"
        "PosixEventEngine::PosixEventEngine()\n"
        "    : executor_(std::make_shared<ThreadPool>()),\n"
        "      timer_manager_(executor_) {}\n"
        "#endif  // GPR_ZEPHYR && GRPC_MINIMAL_CLIENT\n\n"
        "struct PosixEventEngine::ClosureData final",
        "minimal scheduler-only constructor",
    )

    # These virtuals remain present. Connect reports its unsupported operation
    # asynchronously through Run, honoring EventEngine's exactly-once callback
    # contract; the normal TCP implementation is unchanged on other builds.
    source = replace_once(
        source,
        "#else   // GRPC_POSIX_SOCKET_TCP\n"
        "  GPR_ASSERT(false &&\n"
        '             "EventEngine::CancelConnect is not supported on this platform");\n'
        "#endif  // EventEngine POSIX socket machinery",
        "#else   // GRPC_POSIX_SOCKET_TCP\n"
        "#if defined(GPR_ZEPHYR) && defined(GRPC_MINIMAL_CLIENT)\n"
        "  (void)handle;\n"
        "  return false;\n"
        "#else\n"
        "  GPR_ASSERT(false &&\n"
        '             "EventEngine::CancelConnect is not supported on this platform");\n'
        "#endif\n"
        "#endif  // EventEngine POSIX socket machinery",
        "CancelConnect fallback",
    )
    source = replace_once(
        source,
        "#else   // GRPC_POSIX_SOCKET_TCP\n"
        '  GPR_ASSERT(false && "EventEngine::Connect is not supported on this platform");\n'
        "#endif  // EventEngine POSIX socket machinery",
        "#else   // GRPC_POSIX_SOCKET_TCP\n"
        "#if defined(GPR_ZEPHYR) && defined(GRPC_MINIMAL_CLIENT)\n"
        "  (void)addr;\n"
        "  (void)args;\n"
        "  (void)memory_allocator;\n"
        "  (void)timeout;\n"
        "  Run([on_connect = std::move(on_connect)]() mutable {\n"
        "    on_connect(absl::UnimplementedError(\n"
        '        "EventEngine socket Connect is disabled in the minimal Zephyr client"));\n'
        "  });\n"
        "  return {0, 0};\n"
        "#else\n"
        '  GPR_ASSERT(false && "EventEngine::Connect is not supported on this platform");\n'
        "#endif\n"
        "#endif  // EventEngine POSIX socket machinery",
        "Connect fallback",
    )

    if source.count(MARKER) != 5:
        raise SystemExit(
            "unexpected pinned posix_engine.cc socket guard layout "
            f"({source.count(MARKER)} guarded blocks)"
        )
    write_text_if_changed(path, source, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grpc_source", type=Path)
    root = parser.parse_args().grpc_source
    patch_header(root / "src/core/lib/event_engine/posix_engine/posix_engine.h")
    patch_source(root / "src/core/lib/event_engine/posix_engine/posix_engine.cc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
