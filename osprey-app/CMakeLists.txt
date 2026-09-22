cmake_minimum_required(VERSION 3.20.0)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BOARD nucleo_h723zg) # default board

# Pull in the sibling helium-lib as an out-of-tree Zephyr module
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../helium-lib)

# Fetch the sources before Zephyr discovers modules and their Kconfig options.
# Zephyr builds the library later, using the target's toolchain and
# configuration.
include(FetchContent)
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

# Upstream socket-type fix for newer Zephyr releases. Remove this patch when
# updating open62541 to a release that contains the commit below.
find_package(Git REQUIRED)
set(open62541_fix 938fcc53866d1e7d572b07a3bfe6c9f134240262)
FetchContent_Declare(open62541_zephyr_patch
    URL
        "https://github.com/open62541/open62541/commit/${open62541_fix}.patch"
    URL_HASH
        SHA256=b48d535a03b3ffaca70eb5358c40dce8e861839611718c68a7e1d33c4738fc76
    DOWNLOAD_NO_EXTRACT TRUE
    DOWNLOAD_NAME zephyr-fd-set.patch
)
FetchContent_MakeAvailable(open62541_zephyr_patch)

FetchContent_Declare(open62541
    URL https://codeload.github.com/open62541/open62541/tar.gz/refs/tags/v1.5.8
    URL_HASH
        SHA256=cf7951baf253c0537b3397e4ce3ff13930542abcb6ffc3b9cb082af88f95c300
    # Keep Git from discovering the enclosing firmware repository and skipping
    # patch paths that belong to the downloaded library.
    PATCH_COMMAND ${CMAKE_COMMAND} -E env
        "GIT_CEILING_DIRECTORIES=<SOURCE_DIR>/.."
        "${GIT_EXECUTABLE}" apply
        "${open62541_zephyr_patch_SOURCE_DIR}/zephyr-fd-set.patch"
    # This directory has no CMakeLists.txt, so MakeAvailable only downloads it.
    SOURCE_SUBDIR arch/zephyr
)
FetchContent_MakeAvailable(open62541)
list(APPEND EXTRA_ZEPHYR_MODULES "${open62541_SOURCE_DIR}/arch")

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(osprey-app)

file(GLOB app_sources src/*.c)
target_sources(app PRIVATE ${app_sources})
target_link_libraries(app PRIVATE open62541)
