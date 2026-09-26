#!/usr/bin/env python3
"""Generate transport service stubs without touching unchanged outputs."""

import argparse
from pathlib import Path
import subprocess
import tempfile

from generate_proto import include_roots, sync_generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--protobuf", required=True, type=Path)
    parser.add_argument("--protoc", required=True, type=Path)
    parser.add_argument("--plugin", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="grpc-", dir=args.output) as temporary:
        command = [str(args.protoc.resolve(strict=True))]
        command.extend(f"-I{root}" for root in include_roots(source, args.protobuf))
        command.extend([
            f"--plugin=protoc-gen-grpc={args.plugin.resolve(strict=True)}",
            f"--grpc_out={temporary}",
        ])
        protos = sorted((source / "core/pkg/transport/grpc").rglob("*.proto"))
        if not protos:
            raise SystemExit("No Synnax transport schemas found")
        command.extend(str(path) for path in protos)
        subprocess.run(command, check=True)
        sync_generated(Path(temporary), args.output)


if __name__ == "__main__":
    main()
