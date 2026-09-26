include(FetchContent)
find_package(Python3 COMPONENTS Interpreter REQUIRED)
option(OSPREY_SYNNAX_MINIMAL_GRPC
    "Strip optional gRPC features, experiments and tracing on Zephyr" ON)
option(OSPREY_SYNNAX_GRPC_NO_EXCEPTIONS
    "Compile gRPC without C++ exception cleanup to reduce flash (OOM is fatal)" ON)
option(OSPREY_SYNNAX_CLIENT_ONLY_STUBS
    "Generate RPC client implementations without unused server implementations" ON)
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()
if(POLICY CMP0169)
    cmake_policy(SET CMP0169 OLD)
endif()

set(gRPC_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(gRPC_BUILD_CODEGEN OFF CACHE BOOL "" FORCE)
set(gRPC_BUILD_GRPC_CPP_PLUGIN OFF CACHE BOOL "" FORCE)
set(gRPC_BUILD_CSHARP_EXT OFF CACHE BOOL "" FORCE)
set(gRPC_INSTALL OFF CACHE BOOL "" FORCE)
set(gRPC_PROTOBUF_PROVIDER none CACHE STRING "" FORCE)
set(gRPC_ABSL_PROVIDER module CACHE STRING "" FORCE)
set(gRPC_SSL_PROVIDER none CACHE STRING "" FORCE)
set(gRPC_CARES_PROVIDER none CACHE STRING "" FORCE)
set(gRPC_RE2_PROVIDER none CACHE STRING "" FORCE)
set(gRPC_ZLIB_PROVIDER none CACHE STRING "" FORCE)

# Reuse the source snapshots downloaded by fetch-dependencies.sh when they are
# present. Normal CMake builds still fetch the same pinned archives below.
set(_grpc_dependency_cache "${CMAKE_CURRENT_LIST_DIR}/../../.cache/synnax-deps")
foreach(_dependency IN ITEMS grpc re2 zlib)
    string(TOUPPER "${_dependency}" _dependency_upper)
    if(NOT FETCHCONTENT_SOURCE_DIR_${_dependency_upper})
        if(EXISTS "${_grpc_dependency_cache}/${_dependency}/CMakeLists.txt")
            set(FETCHCONTENT_SOURCE_DIR_${_dependency_upper}
                "${_grpc_dependency_cache}/${_dependency}")
        endif()
    endif()
endforeach()

FetchContent_Declare(grpc
    URL https://codeload.github.com/grpc/grpc/tar.gz/refs/tags/v1.51.3
    URL_HASH SHA256=feaeeb315133ea5e3b046c2c0231f5b86ef9d297e536a14b73e0393335f8b157
    SOURCE_SUBDIR no-cmake)
FetchContent_Declare(re2
    URL https://codeload.github.com/google/re2/tar.gz/refs/tags/2022-12-01
    URL_HASH SHA256=665b65b6668156db2b46dddd33405cd422bd611352c5052ab3dae6a5fbac5506
    SOURCE_SUBDIR no-cmake)
FetchContent_Declare(zlib
    URL https://codeload.github.com/madler/zlib/tar.gz/refs/tags/v1.2.13
    URL_HASH SHA256=1525952a0a567581792613a9723333d7f8cc20b87a81f920fb8bc7e3f2251428
    SOURCE_SUBDIR no-cmake)
FetchContent_GetProperties(grpc)
if(NOT grpc_POPULATED)
    FetchContent_Populate(grpc)
endif()
FetchContent_GetProperties(re2)
if(NOT re2_POPULATED)
    FetchContent_Populate(re2)
endif()
FetchContent_GetProperties(zlib)
if(NOT zlib_POPULATED)
    FetchContent_Populate(zlib)
endif()

# zlib 1.2.13 predates current CMake's minimum-policy cutoff.
file(READ "${zlib_SOURCE_DIR}/CMakeLists.txt" _zlib_cmake)
string(REPLACE "cmake_minimum_required(VERSION 2.4.4)"
    "cmake_minimum_required(VERSION 3.5)" _zlib_cmake "${_zlib_cmake}")
file(CONFIGURE OUTPUT "${zlib_SOURCE_DIR}/CMakeLists.txt" CONTENT "${_zlib_cmake}" @ONLY)

execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/patch_grpc_zephyr.py" "${grpc_SOURCE_DIR}"
    "${zlib_SOURCE_DIR}"
    RESULT_VARIABLE _grpc_patch_result)
if(NOT _grpc_patch_result EQUAL 0)
    message(FATAL_ERROR "Could not apply Zephyr platform support to gRPC")
endif()
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/patch_grpc_minimal.py" "${grpc_SOURCE_DIR}"
    RESULT_VARIABLE _grpc_minimal_patch_result)
if(NOT _grpc_minimal_patch_result EQUAL 0)
    message(FATAL_ERROR "Could not make optional gRPC features removable")
endif()
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/patch_grpc_sockets.py" "${grpc_SOURCE_DIR}"
    COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/patch_grpc_event_engine.py" "${grpc_SOURCE_DIR}"
    COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/patch_grpc_codegen.py" "${grpc_SOURCE_DIR}"
    COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/patch_synnax_unsecure.py" "${synnax_SOURCE_DIR}"
    RESULT_VARIABLE _synnax_patch_result)
if(NOT _synnax_patch_result EQUAL 0)
    message(FATAL_ERROR "Could not disable unsupported TLS constructors in Synnax gRPC transport")
endif()

# The v1.51.3 CMake provider blocks accept only "module" and "package".
# Setting them to none skips their setup branches. Supply the dependencies we
# retain explicitly, and build only the unsecure targets below.
set(RE2_ROOT_DIR "${re2_SOURCE_DIR}" CACHE PATH "" FORCE)
set(ZLIB_ROOT_DIR "${zlib_SOURCE_DIR}" CACHE PATH "" FORCE)
add_subdirectory("${re2_SOURCE_DIR}" "${re2_BINARY_DIR}" EXCLUDE_FROM_ALL)
add_subdirectory("${zlib_SOURCE_DIR}" "${zlib_BINARY_DIR}" EXCLUDE_FROM_ALL)

set(_gRPC_RE2_LIBRARIES re2)
set(_gRPC_RE2_INCLUDE_DIR "${re2_SOURCE_DIR}")
set(_gRPC_ZLIB_LIBRARIES zlibstatic)
set(_gRPC_ZLIB_INCLUDE_DIR "${zlib_SOURCE_DIR}" "${zlib_BINARY_DIR}")
set(_gRPC_PROTOBUF_LIBRARIES protobuf::libprotobuf)
set(_gRPC_PROTOBUF_INCLUDE_DIR "${protobuf_SOURCE_DIR}/src")
set(_gRPC_PROTOBUF_LIBRARY_NAME libprotobuf)

# gRPC's generic POSIX CMake path links librt and probes pthreads. Zephyr's
# POSIX layer provides pthreads but has no librt; do not add host-only rt.
set(CMAKE_HAVE_LIBC_PTHREAD ON CACHE BOOL "" FORCE)
set(THREADS_PREFER_PTHREAD_FLAG OFF)
add_compile_definitions(GRPC_ARES=0)

# CMake classifies Zephyr as generic POSIX in its upstream source selection.
# Exclude the secure targets from the default build; users link only the
# unsecure C++ client target, which avoids BoringSSL/TLS.
add_subdirectory("${grpc_SOURCE_DIR}" "${grpc_BINARY_DIR}" EXCLUDE_FROM_ALL)

if(TARGET grpc_unsecure)
    target_compile_definitions(grpc_unsecure PUBLIC GRPC_ARES=0 GPR_ZEPHYR=1)
    if(OSPREY_SYNNAX_MINIMAL_GRPC)
        target_compile_definitions(grpc_unsecure PUBLIC GRPC_MINIMAL_CLIENT=1)
    endif()
    get_target_property(_grpc_core_links grpc_unsecure LINK_LIBRARIES)
    list(REMOVE_ITEM _grpc_core_links rt)
    set_property(TARGET grpc_unsecure PROPERTY LINK_LIBRARIES "${_grpc_core_links}")
endif()
if(TARGET grpc++_unsecure)
    target_compile_definitions(grpc++_unsecure PUBLIC GRPC_ARES=0 GPR_ZEPHYR=1)
    get_target_property(_grpc_cpp_links grpc++_unsecure LINK_LIBRARIES)
    list(REMOVE_ITEM _grpc_cpp_links rt)
    set_property(TARGET grpc++_unsecure PROPERTY LINK_LIBRARIES "${_grpc_cpp_links}")
endif()
if(OSPREY_SYNNAX_GRPC_NO_EXCEPTIONS)
    # The pinned gRPC sources use status returns, not C++ throws. Keep
    # exceptions enabled in Synnax and the application; a failure to allocate
    # within gRPC cannot safely unwind through these library frames.
    foreach(_grpc_target IN ITEMS grpc_unsecure grpc++_unsecure gpr)
        target_compile_options(${_grpc_target} PRIVATE
            $<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions>
            $<$<COMPILE_LANGUAGE:CXX>:-fno-unwind-tables>)
    endforeach()
endif()

# grpc_cpp_plugin is a build-machine tool. Compile its two required sources
# with the native compiler and link to the host protoc libraries built by the
# dependency bootstrap script; never make it part of the ARM firmware.
set(_grpc_native_build "${CMAKE_BINARY_DIR}/host/grpc-plugin")
get_filename_component(_grpc_native_protobuf_build "${SYNNAX_PROTOC_EXECUTABLE}" DIRECTORY)
find_program(_grpc_host_cc NAMES cc clang gcc NO_CMAKE_FIND_ROOT_PATH REQUIRED)
find_program(_grpc_host_cxx NAMES c++ clang++ g++ NO_CMAKE_FIND_ROOT_PATH REQUIRED)
execute_process(COMMAND "${CMAKE_COMMAND}"
    -S "${CMAKE_CURRENT_LIST_DIR}/grpc-plugin" -B "${_grpc_native_build}" -G Ninja
    "-DCMAKE_C_COMPILER=${_grpc_host_cc}"
    "-DCMAKE_CXX_COMPILER=${_grpc_host_cxx}"
    "-DGRPC_SOURCE_DIR=${grpc_SOURCE_DIR}"
    "-DPROTOBUF_SOURCE_DIR=${protobuf_SOURCE_DIR}"
    "-DPROTOBUF_NATIVE_BUILD_DIR=${_grpc_native_protobuf_build}"
    "-DOSPREY_GRPC_CLIENT_ONLY=${OSPREY_SYNNAX_CLIENT_ONLY_STUBS}"
    RESULT_VARIABLE _grpc_host_configure)
if(NOT _grpc_host_configure EQUAL 0)
    message(FATAL_ERROR "Could not configure native grpc_cpp_plugin build")
endif()
execute_process(COMMAND "${CMAKE_COMMAND}" --build "${_grpc_native_build}"
    --target grpc_cpp_plugin --parallel 4
    RESULT_VARIABLE _grpc_host_build)
if(NOT _grpc_host_build EQUAL 0)
    message(FATAL_ERROR "Could not build native grpc_cpp_plugin")
endif()
set(_grpc_cpp_plugin "${_grpc_native_build}/grpc_cpp_plugin")

# Generate only service stubs from the transport proto files. The shared
# generate_proto.py script already emits all message sources.
file(GLOB_RECURSE _synnax_transport_protos CONFIGURE_DEPENDS
    "${synnax_SOURCE_DIR}/core/pkg/transport/grpc/*.proto")
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/generate_grpc.py"
    --source "${synnax_SOURCE_DIR}" --protobuf "${protobuf_SOURCE_DIR}"
    --protoc "${SYNNAX_PROTOC_EXECUTABLE}" --plugin "${_grpc_cpp_plugin}"
    --output "${_synnax_generated}"
    RESULT_VARIABLE _synnax_grpc_codegen)
if(NOT _synnax_grpc_codegen EQUAL 0)
    message(FATAL_ERROR "Synnax gRPC stub generation failed")
endif()

file(GLOB_RECURSE _synnax_grpc_sources CONFIGURE_DEPENDS
    "${_synnax_generated}/core/pkg/transport/grpc/*.grpc.pb.cc")
target_sources(synnax_proto PRIVATE ${_synnax_grpc_sources})
target_link_libraries(synnax_proto PUBLIC grpc++_unsecure)
target_link_libraries(synnax_client PUBLIC grpc++_unsecure)
target_sources(synnax_client PRIVATE "${synnax_SOURCE_DIR}/client/cpp/transport.cpp")

if(COMMAND synnax_zephyr_targets)
    # gRPC v1.51.3 uses the plain target_link_libraries signature for its
    # static targets. The shared helper uses PRIVATE, which CMake rejects as
    # soon as a target has already used the plain signature. Preserve the
    # upstream signature while attaching Zephyr's compiler/link settings.
    function(synnax_zephyr_grpc_targets directory)
        get_property(_targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
        foreach(_target IN LISTS _targets)
            get_target_property(_type "${_target}" TYPE)
            if(_type STREQUAL "STATIC_LIBRARY" OR _type STREQUAL "OBJECT_LIBRARY")
                target_link_libraries("${_target}" zephyr_interface)
                add_dependencies("${_target}" zephyr_generated_headers)
            endif()
        endforeach()
        get_property(_children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
        foreach(_child IN LISTS _children)
            synnax_zephyr_grpc_targets("${_child}")
        endforeach()
    endfunction()
    synnax_zephyr_grpc_targets("${grpc_SOURCE_DIR}")
    synnax_zephyr_targets("${re2_SOURCE_DIR}")
    synnax_zephyr_targets("${zlib_SOURCE_DIR}")
endif()
