#!/usr/bin/env python3
"""Remove host timezone-file backends from Abseil CCTZ on Zephyr."""

from __future__ import annotations

import argparse
from pathlib import Path

from patch_io import write_text_if_changed


MARKER = "OSPREY: omit file-backed CCTZ zone sources on Zephyr"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected one {label}, found {count}")
    return source.replace(old, new, 1)


def patch_time_zone_info(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return

    source = replace_once(
        source,
        "#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n",
        f"#if !defined(__ZEPHYR__)  // {MARKER}\n"
        "#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n"
        "#endif\n",
        "stdio/string headers",
    )
    source = replace_once(
        source,
        "#include <fstream>\n",
        f"#if !defined(__ZEPHYR__)  // {MARKER}\n"
        "#include <fstream>\n"
        "#endif\n",
        "fstream header",
    )
    source = replace_once(
        source,
        "#include <sstream>\n",
        f"#if !defined(__ZEPHYR__)  // {MARKER}\n"
        "#include <sstream>\n"
        "#endif\n",
        "sstream header",
    )

    native_sources = (
        "namespace {\n\n"
        "using FilePtr = std::unique_ptr<FILE, int (*)(FILE*)>;"
    )
    source = replace_once(
        source,
        native_sources,
        f"#if !defined(__ZEPHYR__)  // {MARKER}\n"
        "namespace {\n\n"
        "using FilePtr = std::unique_ptr<FILE, int (*)(FILE*)>;",
        "native zone-source namespace",
    )
    source = replace_once(
        source,
        "}  // namespace\n\n"
        "// What (no leap-seconds) UTC+seconds zoneinfo would look like.",
        "}  // namespace\n"
        "#endif  // !__ZEPHYR__ file-backed zone sources\n\n"
        "// What (no leap-seconds) UTC+seconds zoneinfo would look like.",
        "native zone-source namespace end",
    )

    # Keep fixed UTC and offset names before this code. A custom source factory
    # remains available, but the default Zephyr fallback cannot probe files.
    source = replace_once(
        source,
        "name, [](const std::string& n) -> std::unique_ptr<ZoneInfoSource> {\n"
        "        if (auto z = FileZoneInfoSource::Open(n)) return z;\n"
        "        if (auto z = AndroidZoneInfoSource::Open(n)) return z;\n"
        "        if (auto z = FuchsiaZoneInfoSource::Open(n)) return z;\n"
        "        return nullptr;\n"
        "      });",
        "name, [](const std::string& n) -> std::unique_ptr<ZoneInfoSource> {\n"
        "#if defined(__ZEPHYR__)\n"
        "        (void)n;\n"
        "        return nullptr;\n"
        "#else\n"
        "        if (auto z = FileZoneInfoSource::Open(n)) return z;\n"
        "        if (auto z = AndroidZoneInfoSource::Open(n)) return z;\n"
        "        if (auto z = FuchsiaZoneInfoSource::Open(n)) return z;\n"
        "        return nullptr;\n"
        "#endif\n"
        "      });",
        "default zone-source factory callback",
    )

    source = replace_once(
        source,
        "std::string TimeZoneInfo::Description() const {\n"
        "  std::ostringstream oss;\n"
        '  oss << "#trans=" << transitions_.size();\n'
        '  oss << " #types=" << transition_types_.size();\n'
        '  oss << " spec=\'" << future_spec_ << "\'";\n'
        "  return oss.str();\n"
        "}",
        "std::string TimeZoneInfo::Description() const {\n"
        "#if defined(__ZEPHYR__)\n"
        '  return "#trans=" + std::to_string(transitions_.size()) +\n'
        '         " #types=" + std::to_string(transition_types_.size()) +\n'
        '         " spec=\'" + future_spec_ + "\'";\n'
        "#else\n"
        "  std::ostringstream oss;\n"
        '  oss << "#trans=" << transitions_.size();\n'
        '  oss << " #types=" << transition_types_.size();\n'
        '  oss << " spec=\'" << future_spec_ << "\'";\n'
        "  return oss.str();\n"
        "#endif\n"
        "}",
        "timezone description formatter",
    )

    write_text_if_changed(path, source, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("abseil_source", type=Path)
    root = parser.parse_args().abseil_source
    patch_time_zone_info(
        root / "absl/time/internal/cctz/src/time_zone_info.cc"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
