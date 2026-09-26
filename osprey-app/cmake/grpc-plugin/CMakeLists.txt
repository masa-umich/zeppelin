cmake_minimum_required(VERSION 3.20)
project(osprey_host_grpc_plugin LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(OSPREY_GRPC_CLIENT_ONLY "Omit generated RPC server implementations" ON)

add_executable(grpc_cpp_plugin
    "${GRPC_SOURCE_DIR}/src/compiler/cpp_plugin.cc"
    "${GRPC_SOURCE_DIR}/src/compiler/cpp_generator.cc")
target_include_directories(grpc_cpp_plugin PRIVATE
    "${GRPC_SOURCE_DIR}"
    "${GRPC_SOURCE_DIR}/include"
    "${PROTOBUF_SOURCE_DIR}/src")
if(OSPREY_GRPC_CLIENT_ONLY)
    target_compile_definitions(grpc_cpp_plugin PRIVATE OSPREY_GRPC_CLIENT_ONLY=1)
endif()
target_link_libraries(grpc_cpp_plugin PRIVATE
    "${PROTOBUF_NATIVE_BUILD_DIR}/libprotoc.a"
    "${PROTOBUF_NATIVE_BUILD_DIR}/libprotobuf.a")
