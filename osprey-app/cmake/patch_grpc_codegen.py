#!/usr/bin/env python3
"""Allow the Zephyr gRPC plugin to omit generated server implementations."""

from __future__ import annotations

import argparse
from pathlib import Path

from patch_io import write_text_if_changed


START = '  printer->Print(*vars, "$ns$$Service$::Service::Service() {\\n");\n'
END = """  for (int i = 0; i < service->method_count(); ++i) {
    (*vars)["Idx"] = as_string(i);
    PrintSourceServerMethod(printer, service->method(i).get(), vars);
  }
"""


def patch(source: str, path: Path) -> str:
    source_guard = (
        "#if !defined(OSPREY_GRPC_CLIENT_ONLY)  // OSPREY client-only generation"
    )
    if source_guard not in source:
        if source.count(START) != 1:
            raise SystemExit(f"expected one server implementation start in {path}")
        start = source.index(START)
        end = source.find(END, start)
        if end < 0:
            raise SystemExit(f"could not find server method emission end in {path}")
        end += len(END)
        source = (
            source[:start]
            + f"{source_guard}\n"
            + source[start:end]
            + "#endif  // !defined(OSPREY_GRPC_CLIENT_ONLY)\n"
            + source[end:]
        )

    header_server_start = "  // Server side - base\n"
    header_server_end = '  printer->Print(" StreamedService;\\n");\n'
    header_guard = (
        "  // OSPREY_GRPC_CLIENT_ONLY omits the generated server API.\n"
        "#if !defined(OSPREY_GRPC_CLIENT_ONLY)\n"
    )
    if header_guard not in source:
        if source.count(header_server_start) != 1 or source.count(header_server_end) != 1:
            raise SystemExit(f"could not locate PrintHeaderService server section in {path}")
        start = source.index(header_server_start)
        end = source.index(header_server_end, start) + len(header_server_end)
        source = source[:start] + header_guard + source[start:end] + \
            "#endif  // !defined(OSPREY_GRPC_CLIENT_ONLY)\n" + source[end:]

    # Server-only headers are omitted only in the client-only native plugin;
    # the normal generator retains its complete server API and dependencies.
    header_common = '''    static const char* headers_strs[] = {
        "functional",
        "grpcpp/generic/async_generic_service.h",
        "grpcpp/support/async_stream.h",
        "grpcpp/support/async_unary_call.h",
        "grpcpp/support/client_callback.h",
        "grpcpp/client_context.h",
        "grpcpp/completion_queue.h",
        "grpcpp/support/message_allocator.h",
        "grpcpp/support/method_handler.h",
        "grpcpp/impl/codegen/proto_utils.h",
        "grpcpp/impl/rpc_method.h",
        "grpcpp/support/server_callback.h",
        "grpcpp/impl/codegen/server_callback_handlers.h",
        "grpcpp/server_context.h",
        "grpcpp/impl/service_type.h",
        "grpcpp/impl/codegen/status.h",
        "grpcpp/support/stub_options.h",
        "grpcpp/support/sync_stream.h",
    };
'''
    header_client_only = '''    static const char* headers_strs[] = {
        "functional",
        "grpcpp/support/async_stream.h",
        "grpcpp/support/async_unary_call.h",
        "grpcpp/support/client_callback.h",
        "grpcpp/client_context.h",
        "grpcpp/completion_queue.h",
        "grpcpp/support/message_allocator.h",
        "grpcpp/impl/codegen/proto_utils.h",
        "grpcpp/impl/rpc_method.h",
        "grpcpp/impl/codegen/status.h",
        "grpcpp/support/stub_options.h",
        "grpcpp/support/sync_stream.h",
#if !defined(OSPREY_GRPC_CLIENT_ONLY)
        "grpcpp/generic/async_generic_service.h",
        "grpcpp/support/method_handler.h",
        "grpcpp/support/server_callback.h",
        "grpcpp/impl/codegen/server_callback_handlers.h",
        "grpcpp/server_context.h",
        "grpcpp/impl/service_type.h",
#endif
    };
'''
    if header_common in source:
        source = source.replace(header_common, header_client_only, 1)
    elif header_client_only not in source:
        raise SystemExit(f"could not locate GetHeaderIncludes server headers in {path}")

    source_common = '''        "grpcpp/support/message_allocator.h",
        "grpcpp/support/method_handler.h",
        "grpcpp/impl/rpc_service_method.h",
        "grpcpp/support/server_callback.h",
        "grpcpp/impl/codegen/server_callback_handlers.h",
        "grpcpp/server_context.h",
        "grpcpp/impl/service_type.h",
        "grpcpp/support/sync_stream.h"};
'''
    source_client_only = '''        "grpcpp/support/message_allocator.h",
        "grpcpp/support/sync_stream.h",
#if !defined(OSPREY_GRPC_CLIENT_ONLY)
        "grpcpp/support/method_handler.h",
        "grpcpp/impl/rpc_service_method.h",
        "grpcpp/support/server_callback.h",
        "grpcpp/impl/codegen/server_callback_handlers.h",
        "grpcpp/server_context.h",
        "grpcpp/impl/service_type.h",
#endif
    };
'''
    if source_common in source:
        source = source.replace(source_common, source_client_only, 1)
    elif source_client_only not in source:
        raise SystemExit(f"could not locate GetSourceIncludes server headers in {path}")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grpc_source", type=Path)
    root = parser.parse_args().grpc_source
    path = root / "src/compiler/cpp_generator.cc"
    source = path.read_text(encoding="utf-8")
    write_text_if_changed(path, patch(source, path), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
