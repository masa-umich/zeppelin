#!/usr/bin/env python3
"""Make gRPC's optional channel features removable for the Zephyr client."""

from __future__ import annotations

import argparse
from pathlib import Path


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grpc_source", type=Path)
    source_path = parser.parse_args().grpc_source / "src/core/plugin_registry/grpc_plugin_registry.cc"
    source = source_path.read_text(encoding="utf-8")

    for registration in OPTIONAL_REGISTRATIONS:
        guarded = f"{GUARD_PREFIX}  {registration}\n#endif\n"
        if guarded in source:
            continue
        line = f"  {registration}\n"
        if line not in source:
            raise SystemExit(f"could not find gRPC optional registration {registration}")
        source = source.replace(line, guarded, 1)

    source_path.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
