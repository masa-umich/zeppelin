#!/usr/bin/env python3
"""Disable the unused TLS Pool constructors for the plaintext embedded client."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("synnax_source", type=Path)
    args = parser.parse_args()
    header = args.synnax_source / "freighter/cpp/grpc/grpc.h"
    source = header.read_text(encoding="utf-8")

    ca_constructor = re.compile(
        r"    /// @brief Instantiates the GRPC pool to use TLS encryption where the CA\n"
        r"    /// certificate is located at the provided path\.\n"
        r"    explicit Pool\(const std::string &ca_path\) \{.*?\n    \}\n\n",
        re.DOTALL,
    )
    mtls_constructor = re.compile(
        r"    /// @brief instantiates the GRPC pool to use TLS encryption\. An empty ca_path\n"
        r"    /// verifies the server against the system trust store\. The client certificate and\n"
        r"    /// key are loaded from the provided paths when non-empty\.\n"
        r"    Pool\(\n        const std::string &ca_path,.*?\n    \}\n\n",
        re.DOTALL,
    )
    ca_replacement = (
        "    /// TLS credentials are unavailable in the embedded plaintext build.\n"
        "    explicit Pool(const std::string &) {\n"
        '        throw std::invalid_argument("TLS is disabled in the Zephyr client build");\n'
        "    }\n\n"
    )
    mtls_replacement = (
        "    /// TLS credentials are unavailable in the embedded plaintext build.\n"
        "    Pool(const std::string &, const std::string &, const std::string &) {\n"
        '        throw std::invalid_argument("TLS is disabled in the Zephyr client build");\n'
        "    }\n\n"
    )
    # Keep the exception declaration explicit even if a previous run already
    # replaced the TLS constructors. Older upstream grpc.h does not include
    # <memory>, so do not anchor this insertion on a transitive header.
    if "#include <stdexcept>" not in source:
        source = source.replace(
            "#pragma once\n", "#pragma once\n\n#include <stdexcept>\n", 1
        )
    if "TLS is disabled in the Zephyr client build" in source:
        header.write_text(source, encoding="utf-8")
        return 0
    source, ca_count = ca_constructor.subn(ca_replacement, source, count=1)
    source, mtls_count = mtls_constructor.subn(mtls_replacement, source, count=1)
    if ca_count != 1 or mtls_count != 1:
        raise SystemExit(f"expected both TLS Pool constructors in {header}")
    header.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
