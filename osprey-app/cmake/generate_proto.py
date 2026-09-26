#!/usr/bin/env python3
"""Generate Synnax C++ protobuf messages and a CMake source list.

The Synnax transport protos import message protos from elsewhere in the Synnax
tree, so passing only the transport directory to protoc is not sufficient. This
script finds the transitive import closure and generates every Synnax-owned
message source while leaving Google's well-known types to libprotobuf.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


IMPORT_RE = re.compile(
    r'^\s*import\s+(?:(?:public|weak)\s+)?"([^"]+)"\s*;', re.MULTILINE
)
GOOGLE_PROTOBUF_PREFIX = "google/protobuf/"
OUTPUT_CMAKE = "synnax_proto_sources.cmake"


def write_if_changed(path: Path, content: bytes) -> None:
    if path.exists() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def sync_generated(source: Path, output: Path) -> None:
    # Unchanged generation must not force every client API to recompile.
    for path in source.rglob("*"):
        if path.is_file():
            write_if_changed(output / path.relative_to(source), path.read_bytes())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Synnax source root")
    parser.add_argument(
        "--protobuf", required=True, type=Path, help="protobuf source root or src directory"
    )
    parser.add_argument("--protoc", required=True, type=Path, help="native protoc executable")
    parser.add_argument("--output", required=True, type=Path, help="generated source directory")
    parser.add_argument(
        "--mode",
        choices=("lite", "full"),
        default="lite",
        help="protobuf C++ runtime mode for generated Synnax messages (default: lite)",
    )
    return parser.parse_args()


def include_roots(source: Path, protobuf: Path) -> list[Path]:
    roots = [source]
    # Accept either the protobuf checkout root or its src/ include root.
    if (protobuf / "google" / "protobuf").is_dir():
        roots.append(protobuf)
    if (protobuf / "src" / "google" / "protobuf").is_dir():
        roots.append(protobuf / "src")
    if len(roots) == 1:
        raise FileNotFoundError(
            f"cannot find google/protobuf under protobuf source root {protobuf}"
        )
    return roots


def resolve_import(import_name: str, roots: list[Path]) -> tuple[Path, Path]:
    for root in roots:
        candidate = root / import_name
        if candidate.is_file():
            return root, candidate.resolve()
    roots_text = ", ".join(str(root) for root in roots)
    raise FileNotFoundError(f"proto import {import_name!r} not found under: {roots_text}")


def import_closure(roots: list[Path], source: Path) -> list[tuple[Path, Path]]:
    """Return (include root, proto file) pairs for Synnax-owned closure members."""
    pending: list[tuple[Path, Path]] = []
    for proto in sorted((source / "core/pkg/transport/grpc").rglob("*.proto")):
        pending.append((source, proto.resolve()))
    if not pending:
        raise FileNotFoundError(f"no transport protos found below {source / 'core/pkg/transport/grpc'}")

    visited: dict[str, tuple[Path, Path]] = {}
    while pending:
        include_root, proto = pending.pop()
        logical_name = proto.relative_to(include_root).as_posix()
        if logical_name in visited:
            continue
        visited[logical_name] = (include_root, proto)
        contents = proto.read_text(encoding="utf-8")
        for imported_name in IMPORT_RE.findall(contents):
            imported_root, imported_proto = resolve_import(imported_name, roots)
            if imported_name not in visited:
                pending.append((imported_root, imported_proto))

    # Well-known type .proto definitions and generated sources are supplied by
    # protobuf itself. Pass all Synnax-owned imports to protoc so their generated
    # C++ classes are available to the transport messages.
    return [
        visited[name]
        for name in sorted(visited)
        if not name.startswith(GOOGLE_PROTOBUF_PREFIX)
    ]


def cmake_quote(path: str) -> str:
    return path.replace("\\", "/").replace('"', '\\"')


def main() -> int:
    args = parse_args()
    source = args.source.resolve(strict=True)
    protobuf = args.protobuf.resolve(strict=True)
    if args.protoc.parent == Path("."):
        protoc_path = shutil.which(str(args.protoc))
        if protoc_path is None:
            raise FileNotFoundError(f"native protoc executable not found: {args.protoc}")
        protoc = Path(protoc_path).resolve(strict=True)
    else:
        protoc = args.protoc.resolve(strict=True)
    output = args.output.resolve()

    roots = include_roots(source, protobuf)
    protos = import_closure(roots, source)
    output.mkdir(parents=True, exist_ok=True)

    command = [str(protoc)]
    for root in roots:
        command.append(f"-I{root}")
    with tempfile.TemporaryDirectory(prefix="proto-", dir=output) as temporary:
        generated = Path(temporary)
        cpp_out = f"lite:{generated}" if args.mode == "lite" else str(generated)
        command.append(f"--cpp_out={cpp_out}")
        command.extend(str(proto) for _, proto in protos)
        subprocess.run(command, check=True)
        sync_generated(generated, output)

    generated_sources = [
        (proto.relative_to(include_root).as_posix()[:-len(".proto")] + ".pb.cc")
        for include_root, proto in protos
    ]
    cmake_file = output / OUTPUT_CMAKE
    entries = "\n".join(
        f'    "${{CMAKE_CURRENT_LIST_DIR}}/{cmake_quote(path)}"'
        for path in generated_sources
    )
    write_if_changed(cmake_file, (
        "# Generated by generate_proto.py; do not edit.\n"
        "set(SYNNAX_PROTO_SOURCES\n"
        f"{entries}\n"
        ")\n"
    ).encode())
    print(f"Generated {len(generated_sources)} Synnax protobuf sources in {output}")
    print(f"Wrote {cmake_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"generate_proto.py: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
