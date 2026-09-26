#!/usr/bin/env python3
"""Move Synnax's inline constructor into a Zephyr-only translation unit."""

from __future__ import annotations

import argparse
from pathlib import Path

from patch_io import write_text_if_changed


MARKER = "OSPREY: out-of-line constructor for Zephyr"
CONSTRUCTOR = "explicit Synnax(const Config &cfg):"
NEXT_MEMBER = "Synnax(Synnax &&) = default;"


def brace_pairs(text: str) -> list[tuple[int, int]]:
    """Return C++ brace pairs, ignoring ordinary comments and string literals."""
    pairs: list[tuple[int, int]] = []
    stack: list[int] = []
    i = 0
    state = "code"
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "line_comment":
            if ch == "\n":
                state = "code"
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state in ("string", "character"):
            if ch == "\\":
                i += 1
            elif (state == "string" and ch == '"') or (
                state == "character" and ch == "'"
            ):
                state = "code"
        elif ch == "/" and nxt == "/":
            state = "line_comment"
            i += 1
        elif ch == "/" and nxt == "*":
            state = "block_comment"
            i += 1
        elif ch == '"':
            state = "string"
        elif ch == "'":
            state = "character"
        elif ch == "{":
            stack.append(i)
        elif ch == "}":
            if not stack:
                raise SystemExit("unmatched closing brace while parsing constructor")
            pairs.append((stack.pop(), i))
        i += 1
    if stack or state == "block_comment":
        raise SystemExit("unterminated brace/comment while parsing constructor")
    return pairs


def extract_constructor(source: str) -> str:
    start = source.find(CONSTRUCTOR)
    if start < 0:
        raise SystemExit(f"could not find pinned Synnax constructor: {CONSTRUCTOR}")
    boundary = source.find(NEXT_MEMBER, start)
    if boundary < 0:
        raise SystemExit("could not find the member following the Synnax constructor")
    pairs = brace_pairs(source[start:boundary])
    if not pairs:
        raise SystemExit("constructor has no body")
    body_open, body_close = max(pairs, key=lambda pair: pair[1])
    definition = source[start : start + body_close + 1]
    if definition.count(CONSTRUCTOR) != 1:
        raise SystemExit("unexpected constructor signature while extracting body")
    return definition.replace(CONSTRUCTOR, "Synnax::Synnax(const Config &cfg):", 1)


def patch_header(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    definition = extract_constructor(source)
    if MARKER not in source:
        signature_start = source.find(CONSTRUCTOR)
        boundary = source.find(NEXT_MEMBER, signature_start)
        pairs = brace_pairs(source[signature_start:boundary])
        _, close = max(pairs, key=lambda pair: pair[1])
        end = signature_start + close + 1
        line_start = source.rfind("\n", 0, signature_start) + 1
        indent = source[line_start:signature_start]
        original = source[signature_start:end]
        replacement = (
            "#if defined(__ZEPHYR__)  // "
            f"{MARKER}\n"
            f"{indent}explicit Synnax(const Config &cfg);\n"
            "#else\n"
            + indent
            + original
            + "\n#endif  // __ZEPHYR__ out-of-line constructor"
        )
        source = source[:line_start] + replacement + source[end:]
        write_text_if_changed(path, source, encoding="utf-8")
    return definition


def write_implementation(path: Path, definition: str) -> None:
    output = (
        '#include "client/cpp/synnax.h"\n\n'
        "#if defined(__ZEPHYR__)\n"
        "namespace synnax {\n\n"
        f"{definition}\n\n"
        "}  // namespace synnax\n"
        "#endif  // __ZEPHYR__\n"
    )
    if path.exists():
        write_text_if_changed(path, output, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("synnax_source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    header = args.synnax_source / "client/cpp/synnax.h"
    definition = patch_header(header)
    write_implementation(args.output, definition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
