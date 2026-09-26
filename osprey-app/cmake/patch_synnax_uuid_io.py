#!/usr/bin/env python3
"""Move the UUID ostream overload into its own Zephyr-only source file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from patch_io import write_text_if_changed


MARKER = "OSPREY: isolate UUID ostream operator on Zephyr"
OPERATOR_RE = re.compile(
    r"std::ostream\s*&\s*operator<<\s*\(\s*std::ostream\s*&\s*os,\s*"
    r"const\s+UUID\s*&\s*uuid\s*\)\s*\{\s*"
    r"os\s*<<\s*uuid\.to_string\(\)\s*;\s*"
    r"return\s+os\s*;\s*\}",
    re.MULTILINE,
)
PRESERVED_RE = re.compile(
    r"#if !defined\(__ZEPHYR__\)\s*// "
    + re.escape(MARKER)
    + r"\s*\n(?P<operator>\s*std::ostream\s*&\s*operator<<.*?\n\s*\})\s*"
    r"#endif\s*// !__ZEPHYR__ UUID ostream operator",
    re.DOTALL,
)


def split_uuid_operator(source_path: Path) -> str:
    source = source_path.read_text(encoding="utf-8")
    preserved = PRESERVED_RE.search(source)
    if preserved:
        implementation = preserved.group("operator").strip()
    else:
        matches = list(OPERATOR_RE.finditer(source))
        if len(matches) != 1:
            raise SystemExit(
                f"expected one UUID ostream operator in {source_path}, found {len(matches)}"
            )
        match = matches[0]
        implementation = match.group(0)
        wrapped = (
            f"#if !defined(__ZEPHYR__)  // {MARKER}\n"
            f"{implementation}\n"
            "#endif  // !__ZEPHYR__ UUID ostream operator"
        )
        source = source[: match.start()] + wrapped + source[match.end() :]
        write_text_if_changed(source_path, source, encoding="utf-8")

    # Ensure the preserved branch still contains exactly the overload that is
    # emitted to the Zephyr-only compilation unit.
    if not OPERATOR_RE.fullmatch(implementation):
        raise SystemExit(f"preserved UUID ostream operator in {source_path} changed unexpectedly")
    return implementation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("synnax_source", type=Path, help="Synnax source root")
    parser.add_argument("--output", required=True, type=Path, help="Generated C++ source path")
    args = parser.parse_args()

    source = args.synnax_source / "x/cpp/uuid/uuid.cpp"
    implementation = split_uuid_operator(source)
    generated = (
        '#include "x/cpp/uuid/uuid.h"\n\n'
        "#if defined(__ZEPHYR__)\n"
        "namespace x::uuid {\n\n"
        f"{implementation}\n\n"
        "}  // namespace x::uuid\n"
        "#endif  // __ZEPHYR__\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists() or args.output.read_text(encoding="utf-8") != generated:
        args.output.write_text(generated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
