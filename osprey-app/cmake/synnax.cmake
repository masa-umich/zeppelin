include(FetchContent)
zephyr_compile_definitions(_XOPEN_SOURCE=700)
zephyr_compile_definitions($<$<COMPILE_LANGUAGE:CXX>:_GLIBCXX_HAS_GTHREADS=1>)
zephyr_compile_definitions($<$<COMPILE_LANGUAGE:CXX>:_GLIBCXX_HAVE_TLS=1>)
zephyr_include_directories("${CMAKE_CURRENT_LIST_DIR}/../port/include")
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

# Archives are immutable and checked, including the client rather than tracking main.
# The optional preload file is written by fetch-dependencies.sh for offline builds.
set(_synnax_preload "${CMAKE_CURRENT_LIST_DIR}/../../.cache/synnax-deps/dependencies.cmake")
if(EXISTS "${_synnax_preload}")
    include("${_synnax_preload}")
endif()
FetchContent_Declare(synnax
    URL https://codeload.github.com/synnaxlabs/synnax/tar.gz/37e28149a4dba24c191e6bc7f45bf6a6fb49c5d2
    URL_HASH SHA256=d712c27013e99cd769238851bea58f4e43bf003b06fc0d8181fde6a0c4e6ea78
    SOURCE_SUBDIR no-cmake)
# protobuf 21 retains the same message API while avoiding the newer runtime's
# extra Abseil dependencies. Both native protoc and target runtime use this pin.
FetchContent_Declare(protobuf
    URL https://codeload.github.com/protocolbuffers/protobuf/tar.gz/refs/tags/v21.12
    URL_HASH SHA256=22fdaf641b31655d4b2297f9981fa5203b2866f8332d3c6333f6b0107bb320de
    SOURCE_SUBDIR no-cmake)
FetchContent_Declare(abseil
    URL https://codeload.github.com/abseil/abseil-cpp/tar.gz/refs/tags/20250127.1
    URL_HASH SHA256=b396401fd29e2e679cace77867481d388c807671dc2acc602a0259eeb79b7811
    SOURCE_SUBDIR no-cmake)
FetchContent_Declare(nlohmann_json
    URL https://codeload.github.com/nlohmann/json/tar.gz/refs/tags/v3.12.0
    URL_HASH SHA256=4b92eb0c06d10683f7447ce9406cb97cd4b453be18d7279320f7b2f025c10187
    SOURCE_SUBDIR no-cmake)
FetchContent_Declare(boost_headers
    URL https://archives.boost.io/release/1.88.0/source/boost_1_88_0.tar.bz2
    URL_HASH SHA256=46d9d2c06637b219270877c9e16155cbd015b6dc84349af064c088e9b5b12f7b
    SOURCE_SUBDIR no-cmake)
FetchContent_MakeAvailable(synnax protobuf abseil nlohmann_json boost_headers)

# Patch downloaded trees only. Reverse-check makes reconfiguration idempotent.
find_package(Git REQUIRED)
function(synnax_patch_source source patch)
    set(_git ${CMAKE_COMMAND} -E env "GIT_CEILING_DIRECTORIES=${source}/.." "${GIT_EXECUTABLE}")
    execute_process(COMMAND ${_git} apply --reverse --check "${patch}"
        WORKING_DIRECTORY "${source}" RESULT_VARIABLE _already_applied
        OUTPUT_QUIET ERROR_QUIET)
    if(NOT _already_applied EQUAL 0)
        execute_process(COMMAND ${_git} apply "${patch}"
            WORKING_DIRECTORY "${source}" COMMAND_ERROR_IS_FATAL ANY)
    endif()
endfunction()
synnax_patch_source("${abseil_SOURCE_DIR}" "${CMAKE_CURRENT_LIST_DIR}/patches/abseil-zephyr.patch")
synnax_patch_source("${protobuf_SOURCE_DIR}" "${CMAKE_CURRENT_LIST_DIR}/patches/protobuf-zephyr.patch")
synnax_patch_source("${synnax_SOURCE_DIR}" "${CMAKE_CURRENT_LIST_DIR}/patches/synnax-32bit.patch")
synnax_patch_source("${synnax_SOURCE_DIR}" "${CMAKE_CURRENT_LIST_DIR}/patches/synnax-console.patch")

# Code generation must run on the build machine, never with the ARM compiler.
set(SYNNAX_PROTOC_EXECUTABLE "${SYNNAX_PROTOC_EXECUTABLE}" CACHE FILEPATH "Native protobuf 21.12 protoc")
if(NOT SYNNAX_PROTOC_EXECUTABLE)
    find_program(_synnax_host_cc NAMES cc clang gcc NO_CMAKE_FIND_ROOT_PATH REQUIRED)
    find_program(_synnax_host_cxx NAMES c++ clang++ g++ NO_CMAKE_FIND_ROOT_PATH REQUIRED)
    set(_synnax_host_build "${CMAKE_BINARY_DIR}/host/protobuf")
    set(_synnax_host_log "${CMAKE_BINARY_DIR}/host-protobuf.log")
    message(STATUS "Building native protoc (log: ${_synnax_host_log})")
    execute_process(COMMAND ${CMAKE_COMMAND}
        -S "${protobuf_SOURCE_DIR}/cmake" -B "${_synnax_host_build}" -G Ninja
        "-DCMAKE_C_COMPILER=${_synnax_host_cc}"
        "-DCMAKE_CXX_COMPILER=${_synnax_host_cxx}"
        -DCMAKE_BUILD_TYPE=Release -Dprotobuf_BUILD_TESTS=OFF
        -Dprotobuf_WITH_ZLIB=OFF -Dprotobuf_BUILD_SHARED_LIBS=OFF
        RESULT_VARIABLE _host_config_result OUTPUT_FILE "${_synnax_host_log}"
        ERROR_FILE "${_synnax_host_log}")
    if(NOT _host_config_result EQUAL 0)
        message(FATAL_ERROR "Native protoc configuration failed; see ${_synnax_host_log}")
    endif()
    execute_process(COMMAND ${CMAKE_COMMAND} --build "${_synnax_host_build}"
        --target protoc --parallel 4
        RESULT_VARIABLE _host_build_result OUTPUT_FILE "${_synnax_host_log}"
        ERROR_FILE "${_synnax_host_log}")
    if(NOT _host_build_result EQUAL 0)
        message(FATAL_ERROR "Native protoc build failed; see ${_synnax_host_log}")
    endif()
    set(SYNNAX_PROTOC_EXECUTABLE "${_synnax_host_build}/protoc" CACHE FILEPATH "" FORCE)
endif()
execute_process(COMMAND "${SYNNAX_PROTOC_EXECUTABLE}" --version
    OUTPUT_VARIABLE _protoc_version OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE _protoc_result)
if(NOT _protoc_result EQUAL 0 OR NOT _protoc_version STREQUAL "libprotoc 3.21.12")
    message(FATAL_ERROR "Synnax requires native protoc 3.21.12, got '${_protoc_version}'")
endif()

set(_synnax_generated "${CMAKE_BINARY_DIR}/synnax-generated")
option(OSPREY_SYNNAX_LITE_PROTO
    "Generate Synnax-owned protobuf messages with the smaller MessageLite runtime"
    ON)
if(OSPREY_SYNNAX_LITE_PROTO)
    set(_synnax_proto_mode lite)
else()
    set(_synnax_proto_mode full)
endif()
execute_process(COMMAND "${PYTHON_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/generate_proto.py"
    --source "${synnax_SOURCE_DIR}" --protobuf "${protobuf_SOURCE_DIR}"
    --protoc "${SYNNAX_PROTOC_EXECUTABLE}" --output "${_synnax_generated}"
    --mode "${_synnax_proto_mode}"
    COMMAND_ERROR_IS_FATAL ANY)
include("${_synnax_generated}/synnax_proto_sources.cmake")
# Upstream errors.h uses Bazel's nested generated-header layout.
file(MAKE_DIRECTORY "${_synnax_generated}/x/go/errors/x/go/errors")
file(CONFIGURE OUTPUT "${_synnax_generated}/x/go/errors/x/go/errors/errors.pb.h"
    CONTENT "#pragma once\n#include \"x/go/errors/errors.pb.h\"\n" @ONLY)
file(READ "${synnax_SOURCE_DIR}/client/cpp/version/VERSION" _synnax_version)
string(STRIP "${_synnax_version}" _synnax_version)
file(MAKE_DIRECTORY "${_synnax_generated}/client/cpp/version")
file(CONFIGURE OUTPUT "${_synnax_generated}/client/cpp/version/version.h"
    CONTENT "#pragma once\n#define SYNNAX_CLIENT_VERSION \"${_synnax_version}\"\n" @ONLY)

# Zephyr implements pthreads in its POSIX layer. Avoid a host-library probe.
set(CMAKE_HAVE_LIBC_PTHREAD ON CACHE BOOL "" FORCE)
set(protobuf_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(protobuf_BUILD_PROTOC_BINARIES OFF CACHE BOOL "" FORCE)
set(protobuf_WITH_ZLIB OFF CACHE BOOL "" FORCE)
set(protobuf_BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(protobuf_INSTALL OFF CACHE BOOL "" FORCE)
add_subdirectory("${protobuf_SOURCE_DIR}/cmake" "${protobuf_BINARY_DIR}" EXCLUDE_FROM_ALL)
set(ABSL_BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(ABSL_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
set(ABSL_PROPAGATE_CXX_STD ON CACHE BOOL "" FORCE)
set(CMAKE_CXX_STANDARD 20)
add_subdirectory("${abseil_SOURCE_DIR}" "${abseil_BINARY_DIR}" EXCLUDE_FROM_ALL)

# Imported upstream targets need the same includes, CPU flags, and libc as app.
function(synnax_zephyr_targets directory)
    get_property(_targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
    foreach(_target IN LISTS _targets)
        get_target_property(_type "${_target}" TYPE)
        if(_type STREQUAL "STATIC_LIBRARY" OR _type STREQUAL "OBJECT_LIBRARY")
            # gRPC uses the plain link signature; Abseil uses the keyword form.
            # Appending the property supports both without mixing signatures.
            set_property(TARGET "${_target}" APPEND PROPERTY LINK_LIBRARIES zephyr_interface)
            add_dependencies("${_target}" zephyr_generated_headers)
        endif()
    endforeach()
    get_property(_children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
    foreach(_child IN LISTS _children)
        synnax_zephyr_targets("${_child}")
    endforeach()
endfunction()
synnax_zephyr_targets("${protobuf_SOURCE_DIR}/cmake")
synnax_zephyr_targets("${abseil_SOURCE_DIR}")
# Zephyr has no exec(), so close-on-exec has no effect on this target.
target_compile_definitions(absl_base PRIVATE O_CLOEXEC=0)

add_library(synnax_proto STATIC ${SYNNAX_PROTO_SOURCES})
add_dependencies(synnax_proto zephyr_generated_headers)
target_include_directories(synnax_proto PUBLIC "${_synnax_generated}")
target_link_libraries(synnax_proto PUBLIC protobuf::libprotobuf PRIVATE zephyr_interface)

# Compile every implementation behind the umbrella, except the gRPC transport.
# A static archive plus section GC keeps uncalled APIs out of the smoke firmware.
set(_synnax_client_sources
    client/cpp/arc/arc.cpp
    client/cpp/channel/channel.cpp
    client/cpp/connection/checker.cpp
    client/cpp/device/device.cpp
    client/cpp/framer/codec.cpp
    client/cpp/framer/streamer.cpp
    client/cpp/framer/writer.cpp
    client/cpp/ontology/id.cpp
    client/cpp/rack/rack.cpp
    client/cpp/ranger/ranger.cpp
    client/cpp/ranger/kv/kv.cpp
    client/cpp/task/task.cpp
    client/cpp/view/view.cpp
    x/cpp/telem/frame.cpp
    x/cpp/telem/series.cpp
    x/cpp/uuid/uuid.cpp
    x/cpp/color/color.cpp
    x/cpp/json/convert.cpp
    x/cpp/log/log.cpp
    x/cpp/url/url.cpp
    x/cpp/base64/base64.cpp)
list(TRANSFORM _synnax_client_sources PREPEND "${synnax_SOURCE_DIR}/")
add_library(synnax_client STATIC ${_synnax_client_sources})
add_dependencies(synnax_client zephyr_generated_headers)
target_include_directories(synnax_client PUBLIC
    "${synnax_SOURCE_DIR}" "${_synnax_generated}"
    "${nlohmann_json_SOURCE_DIR}/include" "${boost_headers_SOURCE_DIR}")
target_link_libraries(synnax_client PUBLIC synnax_proto absl::log
    absl::log_initialize absl::log_globals absl::log_sink_registry
    PRIVATE zephyr_interface)

option(OSPREY_SYNNAX_FULL_CLIENT "Build and link the real plaintext gRPC client (experimental)" OFF)
if(OSPREY_SYNNAX_FULL_CLIENT)
    include("${CMAKE_CURRENT_LIST_DIR}/grpc.cmake")
    target_compile_definitions(app PRIVATE OSPREY_SYNNAX_FULL_CLIENT=1)
endif()
