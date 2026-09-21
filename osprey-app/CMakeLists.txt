cmake_minimum_required(VERSION 3.20.0)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BOARD nucleo_h723zg) # default board

# Fetch the sources before Zephyr discovers modules and their Kconfig options.
# Zephyr builds the library later, using the target's toolchain and
# configuration.
include(FetchContent)
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()
FetchContent_Declare(open62541
    URL https://codeload.github.com/open62541/open62541/tar.gz/refs/tags/v1.5.8
    URL_HASH
        SHA256=cf7951baf253c0537b3397e4ce3ff13930542abcb6ffc3b9cb082af88f95c300
    PATCH_COMMAND ${CMAKE_COMMAND} -DOPEN62541_SOURCE_DIR=<SOURCE_DIR>
        -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/patch-open62541.cmake
    # This directory has no CMakeLists.txt, so MakeAvailable only downloads it.
    SOURCE_SUBDIR arch/zephyr
)
FetchContent_MakeAvailable(open62541)
list(APPEND EXTRA_ZEPHYR_MODULES "${open62541_SOURCE_DIR}/arch")

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(osprey-app)

target_sources(app PRIVATE src/main.c)
target_link_libraries(app PRIVATE open62541)
