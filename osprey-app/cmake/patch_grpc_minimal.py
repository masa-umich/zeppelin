#!/usr/bin/env python3
"""Make gRPC's optional channel features removable for the Zephyr client."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from patch_io import write_text_if_changed


OPTIONAL_REGISTRATIONS = (
    "RegisterHttpConnectHandshaker(builder);",
    "RegisterPriorityLbPolicy(builder);",
    "RegisterOutlierDetectionLbPolicy(builder);",
    "RegisterWeightedTargetLbPolicy(builder);",
    "RegisterRoundRobinLbPolicy(builder);",
    "RegisterRingHashLbPolicy(builder);",
    "RegisterGrpcLbPolicy(builder);",
    "FaultInjectionFilterRegister(builder);",
    "RegisterAresDnsResolver(builder);",
    "RegisterFakeResolver(builder);",
    "RegisterHttpProxyMapper(builder);",
    "RegisterRlsLbPolicy(builder);",
    "RegisterExtraFilters(builder);",
)

GUARD_PREFIX = "#if !defined(GPR_ZEPHYR) || !defined(GRPC_MINIMAL_CLIENT)\n"


def freeze_experiments(source_root: Path) -> None:
    """Retain the release defaults without linking both experimental paths."""
    path = source_root / "src/core/lib/experiments/experiments.h"
    source = path.read_text(encoding="utf-8")
    if "OSPREY: fixed release experiment defaults" in source:
        return
    # These are the pinned v1.51.3 release defaults in experiments.cc. In
    # particular, keep legacy socket I/O, calls, and the compact HPACK decoder.
    enabled = {1, 6, 10}
    pattern = r"(inline bool \w+\(\) \{)\s*return IsExperimentEnabled\((\d+)\);\s*\}"

    def replacement(match: re.Match[str]) -> str:
        index = int(match[2])
        default = "true" if index in enabled else "false"
        return (
            f"{match[1]}\n"
            "#if defined(GPR_ZEPHYR) && defined(GRPC_MINIMAL_CLIENT)\n"
            f"  return {default};  // OSPREY: fixed release experiment defaults\n"
            "#else\n"
            f"  return IsExperimentEnabled({index});\n"
            "#endif\n}"
        )

    source, count = re.subn(pattern, replacement, source)
    if count != 13:
        raise SystemExit(f"expected 13 pinned gRPC experiment switches, found {count}")
    write_text_if_changed(path, source, encoding="utf-8")


def disable_tracers(source_root: Path) -> None:
    path = source_root / "src/core/lib/debug/trace.h"
    source = path.read_text(encoding="utf-8")
    marker = "// OSPREY: omit optional trace code in the minimal release client"
    if marker in source:
        return
    original = "#define GRPC_USE_TRACERS  // tracers on by default in OSS"
    if original not in source:
        raise SystemExit("could not find pinned gRPC tracer configuration")
    source = source.replace(
        original,
        f"{marker}\n{GUARD_PREFIX}{original}\n#endif",
        1,
    )
    write_text_if_changed(path, source, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grpc_source", type=Path)
    source_root = parser.parse_args().grpc_source
    source_path = source_root / "src/core/plugin_registry/grpc_plugin_registry.cc"
    source = source_path.read_text(encoding="utf-8")

    for registration in OPTIONAL_REGISTRATIONS:
        guarded = f"{GUARD_PREFIX}  {registration}\n#endif\n"
        if guarded in source:
            continue
        line = f"  {registration}\n"
        if line not in source:
            raise SystemExit(f"could not find gRPC optional registration {registration}")
        source = source.replace(line, guarded, 1)

    write_text_if_changed(source_path, source, encoding="utf-8")
    freeze_experiments(source_root)
    disable_tracers(source_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
