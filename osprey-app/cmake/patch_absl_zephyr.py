#!/usr/bin/env python3
"""Back Abseil LowLevelAlloc with Zephyr's kernel heap on embedded builds."""

from __future__ import annotations

import argparse
from pathlib import Path

from patch_io import write_text_if_changed


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"could not patch {label} in {path}")
    write_text_if_changed(path, text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("abseil_source", type=Path)
    root = parser.parse_args().abseil_source

    # POSIX stderr is not a dependable early-boot console on Zephyr. RawLog
    # must still report allocator/invariant failures before aborting.
    raw_logging = root / "absl/base/internal/raw_logging.cc"
    replace_once(
        raw_logging,
        '#include "absl/base/log_severity.h"\n',
        '#include "absl/base/log_severity.h"\n'
        '#if defined(__ZEPHYR__)\n#include <zephyr/sys/printk.h>\n'
        '#define ABSL_LOW_LEVEL_WRITE_SUPPORTED 1\n#endif\n',
        "Zephyr raw console logging",
    )
    replace_once(
        raw_logging,
        "#elif defined(ABSL_HAVE_POSIX_WRITE)\n  write(STDERR_FILENO, s, len);\n",
        "#elif defined(__ZEPHYR__)\n"
        "  while (len != 0) {\n"
        "    const size_t chunk = len < 128 ? len : 128;\n"
        '    printk("%.*s", static_cast<int>(chunk), s);\n'
        "    s += chunk;\n    len -= chunk;\n  }\n"
        "#elif defined(ABSL_HAVE_POSIX_WRITE)\n  write(STDERR_FILENO, s, len);\n",
        "Zephyr raw console writer",
    )

    # Abseil Mutex and thread identity require LowLevelAlloc. Zephyr's H723 has
    # no MMU-backed mmap, so provide the same arena API using k_malloc/k_free.
    header = root / "absl/base/internal/low_level_alloc.h"
    replace_once(
        header,
        "#elif !defined(ABSL_HAVE_MMAP) && !defined(_WIN32)\n",
        "#elif !defined(ABSL_HAVE_MMAP) && !defined(_WIN32) && \\\n    !defined(__ZEPHYR__)\n",
        "Zephyr LowLevelAlloc availability",
    )
    replace_once(
        header,
        "#elif defined(_WIN32) || defined(__asmjs__) || defined(__wasm__) || \\\n    defined(__hexagon__)\n",
        "#elif defined(_WIN32) || defined(__asmjs__) || defined(__wasm__) || \\\n    defined(__hexagon__) || defined(__ZEPHYR__)\n",
        "Zephyr async-signal-safe allocator exclusion",
    )

    allocator = root / "absl/base/internal/low_level_alloc.cc"
    replace_once(
        allocator,
        "#ifndef _WIN32\n#include <pthread.h>\n#include <signal.h>\n#include <sys/mman.h>\n#include <unistd.h>\n#else\n#include <windows.h>\n#endif\n",
        "#if defined(__ZEPHYR__)\n#include <zephyr/kernel.h>\n#elif !defined(_WIN32)\n#include <pthread.h>\n#include <signal.h>\n#include <sys/mman.h>\n#include <unistd.h>\n#else\n#include <windows.h>\n#endif\n",
        "Zephyr kernel heap include",
    )
    replace_once(
        allocator,
        "#elif defined(__wasm__) || defined(__asmjs__) || defined(__hexagon__)\n  return getpagesize();\n#else\n",
        "#elif defined(__ZEPHYR__)\n  // LowLevelAlloc uses this for 1 KiB growth increments and size checks.\n  return 64;\n#elif defined(__wasm__) || defined(__asmjs__) || defined(__hexagon__)\n  return getpagesize();\n#else\n",
        "Zephyr LowLevelAlloc granularity",
    )
    replace_once(
        allocator,
        "    ABSL_RAW_CHECK(reinterpret_cast<uintptr_t>(region) % arena->pagesize == 0,\n                   \"empty arena has non-page-aligned block\");\n",
        "#ifndef __ZEPHYR__\n    ABSL_RAW_CHECK(reinterpret_cast<uintptr_t>(region) % arena->pagesize == 0,\n                   \"empty arena has non-page-aligned block\");\n#endif\n",
        "Zephyr heap region alignment",
    )

    delete_region_old = '''    int munmap_result;
#ifdef _WIN32
    munmap_result = VirtualFree(region, 0, MEM_RELEASE);
    ABSL_RAW_CHECK(munmap_result != 0,
                   "LowLevelAlloc::DeleteArena: VitualFree failed");
#else
#ifndef ABSL_LOW_LEVEL_ALLOC_ASYNC_SIGNAL_SAFE_MISSING
    if ((arena->flags & LowLevelAlloc::kAsyncSignalSafe) == 0) {
      munmap_result = munmap(region, size);
    } else {
      munmap_result = base_internal::DirectMunmap(region, size);
    }
#else
    munmap_result = munmap(region, size);
#endif  // ABSL_LOW_LEVEL_ALLOC_ASYNC_SIGNAL_SAFE_MISSING
    if (munmap_result != 0) {
      ABSL_RAW_LOG(FATAL, "LowLevelAlloc::DeleteArena: munmap failed: %d",
                   errno);
    }
#endif  // _WIN32
'''
    delete_region_new = '''#if defined(__ZEPHYR__)
    k_free(region->header.dummy_for_alignment);
#elif defined(_WIN32)
    int munmap_result = VirtualFree(region, 0, MEM_RELEASE);
    ABSL_RAW_CHECK(munmap_result != 0,
                   "LowLevelAlloc::DeleteArena: VitualFree failed");
#else
#ifndef ABSL_LOW_LEVEL_ALLOC_ASYNC_SIGNAL_SAFE_MISSING
    int munmap_result;
    if ((arena->flags & LowLevelAlloc::kAsyncSignalSafe) == 0) {
      munmap_result = munmap(region, size);
    } else {
      munmap_result = base_internal::DirectMunmap(region, size);
    }
#else
    int munmap_result = munmap(region, size);
#endif  // ABSL_LOW_LEVEL_ALLOC_ASYNC_SIGNAL_SAFE_MISSING
    if (munmap_result != 0) {
      ABSL_RAW_LOG(FATAL, "LowLevelAlloc::DeleteArena: munmap failed: %d",
                   errno);
    }
#endif  // __ZEPHYR__ / _WIN32
'''
    replace_once(
        allocator,
        delete_region_old,
        delete_region_new,
        "Zephyr heap region release",
    )

    replace_once(
        allocator,
        "#ifdef _WIN32\n      new_pages = VirtualAlloc(nullptr, new_pages_size,\n                               MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);\n      ABSL_RAW_CHECK(new_pages != nullptr, \"VirtualAlloc failed\");\n#else\n",
        "#if defined(__ZEPHYR__)\n      void *heap_region = k_malloc(new_pages_size + 64);\n      ABSL_RAW_CHECK(heap_region != nullptr, \"Zephyr heap exhausted in LowLevelAlloc\");\n      new_pages = static_cast<char *>(heap_region) + 32;\n#elif defined(_WIN32)\n      new_pages = VirtualAlloc(nullptr, new_pages_size,\n                               MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);\n      ABSL_RAW_CHECK(new_pages != nullptr, \"VirtualAlloc failed\");\n#else\n",
        "Zephyr LowLevelAlloc region allocation",
    )
    replace_once(
        allocator,
        "      s->header.arena = arena;\n      AddToFreelist(&s->levels, arena);",
        "      s->header.arena = arena;\n#if defined(__ZEPHYR__)\n      s->header.dummy_for_alignment = heap_region;\n#endif\n      AddToFreelist(&s->levels, arena);",
        "Zephyr LowLevelAlloc original heap pointer",
    )

    # Zephyr pthread keys execute registered destructors when a thread exits.
    # It has no async signal handlers, so skip Abseil's signal masking around
    # pthread_setspecific but retain the regular POSIX destructor path.
    identity_source = root / "absl/base/internal/thread_identity.cc"
    replace_once(
        identity_source,
        "#if defined(__wasi__) || defined(__EMSCRIPTEN__) || defined(__MINGW32__) || \\\n    defined(__hexagon__)\n",
        "#if defined(__wasi__) || defined(__EMSCRIPTEN__) || defined(__MINGW32__) || \\\n    defined(__hexagon__) || defined(__ZEPHYR__)\n",
        "Zephyr pthread-key signal-mask bypass",
    )
    # Remove this branch if an earlier experimental version of the porting
    # script selected C++ TLS destructors; Zephyr's POSIX key destructors are
    # the supported path and avoid a __cxa_thread_atexit dependency.
    identity_header = root / "absl/base/internal/thread_identity.h"
    identity_text = identity_header.read_text(encoding="utf-8")
    old_tls_mode = (
        "#elif defined(__ZEPHYR__)\n"
        "#define ABSL_THREAD_IDENTITY_MODE ABSL_THREAD_IDENTITY_MODE_USE_CPP11\n"
    )
    if old_tls_mode in identity_text:
        write_text_if_changed(identity_header, identity_text.replace(old_tls_mode, "", 1), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
