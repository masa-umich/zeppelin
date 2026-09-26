cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(osprey_abseil_port_test LANGUAGES C CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../../port/runtime.cmake")

include(FetchContent)
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()
if(POLICY CMP0169)
    cmake_policy(SET CMP0169 OLD)
endif()

# Reuse the repository's bootstrap cache when present; otherwise fetch the
# same immutable Abseil release used by the Synnax client.
set(_abseil_cache "${CMAKE_CURRENT_LIST_DIR}/../../../.cache/synnax-deps/abseil_cpp")
if(EXISTS "${_abseil_cache}/CMakeLists.txt")
    set(FETCHCONTENT_SOURCE_DIR_ABSEIL "${_abseil_cache}" CACHE PATH "" FORCE)
endif()
FetchContent_Declare(abseil
    URL https://codeload.github.com/abseil/abseil-cpp/tar.gz/refs/tags/20250127.1
    URL_HASH SHA256=b396401fd29e2e679cace77867481d388c807671dc2acc602a0259eeb79b7811)
FetchContent_GetProperties(abseil)
if(NOT abseil_POPULATED)
    FetchContent_Populate(abseil)
endif()

find_package(Git REQUIRED)
function(abseil_patch_source source patch)
    set(_git ${CMAKE_COMMAND} -E env "GIT_CEILING_DIRECTORIES=${source}/.." "${GIT_EXECUTABLE}")
    execute_process(COMMAND ${_git} apply --reverse --check "${patch}"
        WORKING_DIRECTORY "${source}" RESULT_VARIABLE _already_applied
        OUTPUT_QUIET ERROR_QUIET)
    if(NOT _already_applied EQUAL 0)
        execute_process(COMMAND ${_git} apply "${patch}"
            WORKING_DIRECTORY "${source}" COMMAND_ERROR_IS_FATAL ANY)
    endif()
endfunction()
abseil_patch_source("${abseil_SOURCE_DIR}"
    "${CMAKE_CURRENT_LIST_DIR}/../../cmake/patches/abseil-zephyr.patch")

find_package(Python3 COMPONENTS Interpreter REQUIRED)
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/../../cmake/patch_absl_zephyr.py" "${abseil_SOURCE_DIR}"
    COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_LIST_DIR}/../../cmake/patch_absl_time.py" "${abseil_SOURCE_DIR}"
    COMMAND_ERROR_IS_FATAL ANY)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_HAVE_LIBC_PTHREAD ON CACHE BOOL "" FORCE)
set(ABSL_BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(ABSL_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
set(ABSL_PROPAGATE_CXX_STD ON CACHE BOOL "" FORCE)
add_subdirectory("${abseil_SOURCE_DIR}" "${abseil_BINARY_DIR}" EXCLUDE_FROM_ALL)
target_compile_definitions(absl_base PRIVATE O_CLOEXEC=0)
set(_abseil_port_include "${CMAKE_CURRENT_LIST_DIR}/../../port/include")

function(abseil_zephyr_targets directory)
    get_property(_targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
    foreach(_target IN LISTS _targets)
        get_target_property(_type "${_target}" TYPE)
        if(_type STREQUAL "STATIC_LIBRARY" OR _type STREQUAL "OBJECT_LIBRARY")
            target_link_libraries("${_target}" PRIVATE zephyr_interface)
            target_include_directories("${_target}" BEFORE PRIVATE
                "${_abseil_port_include}")
            target_compile_definitions("${_target}" PRIVATE
                _GLIBCXX_HAS_GTHREADS=1 _GLIBCXX_HAVE_TLS=1)
            add_dependencies("${_target}" zephyr_generated_headers)
        endif()
    endforeach()
    get_property(_children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
    foreach(_child IN LISTS _children)
        abseil_zephyr_targets("${_child}")
    endforeach()
endfunction()
abseil_zephyr_targets("${abseil_SOURCE_DIR}")

zephyr_compile_definitions(_XOPEN_SOURCE=700 NDEBUG=1
    $<$<COMPILE_LANGUAGE:CXX>:_GLIBCXX_HAS_GTHREADS=1>
    $<$<COMPILE_LANGUAGE:CXX>:_GLIBCXX_HAVE_TLS=1>)
option(OSPREY_SYNNAX_STRIP_LOGS
    "Omit Abseil stream logging and CHECK messages (failed checks still abort)" ON)
if(OSPREY_SYNNAX_STRIP_LOGS)
    zephyr_compile_definitions(ABSL_MIN_LOG_LEVEL=4)
endif()
zephyr_include_directories("${_abseil_port_include}")
target_sources(app PRIVATE
    src/main.cpp
    ../../port/std_thread.cpp
    ../../src/atomic64.cpp)
target_link_libraries(app PRIVATE absl::malloc_internal absl::synchronization absl::time)
