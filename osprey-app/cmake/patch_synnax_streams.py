#!/usr/bin/env python3
"""Replace checker stream formatting with small Zephyr-only equivalents."""

from __future__ import annotations

import argparse
from pathlib import Path

from patch_io import write_text_if_changed


OLD_INCLUDES = """#include <chrono>
#include <optional>
#include <sstream>
#include <string>
#include <utility>
"""

NEW_INCLUDES = """#include <chrono>
#include <optional>
#include <string>
#include <utility>

#if defined(__ZEPHYR__)
#include <cerrno>
#include <climits>
#include <cstdlib>
#else
#include <sstream>
#endif
"""

OLD_PARSE = """std::optional<std::pair<int, int>> parse_version(const std::string &v) {
    std::istringstream ss(v);
    int major = 0, minor = 0;
    char dot = 0;
    if (!(ss >> major >> dot >> minor) || dot != '.') return std::nullopt;
    return std::make_pair(major, minor);
}
"""

NEW_PARSE = """#if defined(__ZEPHYR__)
namespace {
bool is_c_whitespace(const char c) {
    return c == ' ' || c == '\\t' || c == '\\n' || c == '\\r' || c == '\\f' ||
           c == '\\v';
}

bool parse_int(const char *&cursor, int &value) {
    errno = 0;
    char *end = nullptr;
    const long parsed = std::strtol(cursor, &end, 10);
    if (end == cursor || errno == ERANGE || parsed < INT_MIN || parsed > INT_MAX)
        return false;
    cursor = end;
    value = static_cast<int>(parsed);
    return true;
}
}  // namespace

std::optional<std::pair<int, int>> parse_version(const std::string &v) {
    const char *cursor = v.c_str();
    int major = 0, minor = 0;
    if (!parse_int(cursor, major)) return std::nullopt;
    while (is_c_whitespace(*cursor)) ++cursor;
    if (*cursor++ != '.') return std::nullopt;
    if (!parse_int(cursor, minor)) return std::nullopt;
    return std::make_pair(major, minor);
}
#else
std::optional<std::pair<int, int>> parse_version(const std::string &v) {
    std::istringstream ss(v);
    int major = 0, minor = 0;
    char dot = 0;
    if (!(ss >> major >> dot >> minor) || dot != '.') return std::nullopt;
    return std::make_pair(major, minor);
}
#endif
"""

OLD_WARNING = """    std::ostringstream ss;
    ss << "The Synnax Core version ";
    if (!node_version.empty()) ss << node_version << " ";
    ss << "is too " << age << " for client version " << client_version
       << ". This may cause compatibility issues. We recommend updating the "
       << to_upgrade << ". For more information, see " << TROUBLESHOOTING_URL << "#old-"
       << slug << "-version";
    return ss.str();
"""

NEW_WARNING = """#if defined(__ZEPHYR__)
    std::string warning = "The Synnax Core version ";
    if (!node_version.empty()) warning += node_version + " ";
    warning += "is too ";
    warning += age;
    warning += " for client version ";
    warning += client_version;
    warning += ". This may cause compatibility issues. We recommend updating the ";
    warning += to_upgrade;
    warning += ". For more information, see ";
    warning += TROUBLESHOOTING_URL;
    warning += "#old-";
    warning += slug;
    warning += "-version";
    return warning;
#else
    std::ostringstream ss;
    ss << "The Synnax Core version ";
    if (!node_version.empty()) ss << node_version << " ";
    ss << "is too " << age << " for client version " << client_version
       << ". This may cause compatibility issues. We recommend updating the "
       << to_upgrade << ". For more information, see " << TROUBLESHOOTING_URL << "#old-"
       << slug << "-version";
    return ss.str();
#endif
"""


def patch(source: str, path: Path) -> str:
    if "OSPREY: lightweight checker formatting" in source:
        return source
    if OLD_INCLUDES not in source:
        raise SystemExit(f"could not find expected checker includes in {path}")
    source = source.replace(OLD_INCLUDES, NEW_INCLUDES, 1)
    if OLD_PARSE not in source:
        raise SystemExit(f"could not find expected parse_version in {path}")
    source = source.replace(OLD_PARSE, NEW_PARSE, 1)
    if OLD_WARNING not in source:
        raise SystemExit(f"could not find expected create_version_warning stream in {path}")
    source = source.replace(OLD_WARNING, NEW_WARNING, 1)
    source = source.replace(
        "namespace synnax::connection {\n",
        "namespace synnax::connection {\n// OSPREY: lightweight checker formatting\n",
        1,
    )
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("synnax_source", type=Path)
    root = parser.parse_args().synnax_source
    path = root / "client/cpp/connection/checker.cpp"
    source = path.read_text(encoding="utf-8")
    write_text_if_changed(path, patch(source, path), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
