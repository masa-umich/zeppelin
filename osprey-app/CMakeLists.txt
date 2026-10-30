cmake_minimum_required(VERSION 3.20.0)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BOARD nucleo_h723zg) # default board

# Pull in the sibling helium-lib as an out-of-tree Zephyr module
list(APPEND EXTRA_ZEPHYR_MODULES "${CMAKE_CURRENT_SOURCE_DIR}/../helium-lib")

# Fetch the sources before Zephyr discovers modules and their Kconfig options.
# Zephyr builds the library later, using the target's toolchain and
# configuration.
include(FetchContent)
set(UA_LOGLEVEL 400 CACHE STRING "open62541 warning and error logging")
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

FetchContent_Declare(open62541
    URL https://codeload.github.com/open62541/open62541/tar.gz/refs/tags/v1.5.8
    URL_HASH
        SHA256=cf7951baf253c0537b3397e4ce3ff13930542abcb6ffc3b9cb082af88f95c300
    # This directory has no CMakeLists.txt, so MakeAvailable only downloads it.
    SOURCE_SUBDIR arch/zephyr
)
FetchContent_MakeAvailable(open62541)

# Upstream fix 938fcc53866d1e7d572b07a3bfe6c9f134240262: zsock_fd_set is
# already a typedef. Apply locally without downloading a patch or invoking Git.
set(open62541_zephyr_header "${open62541_SOURCE_DIR}/arch/zephyr/eventloop_zephyr.h")
file(READ "${open62541_zephyr_header}" open62541_zephyr_source)
if(open62541_zephyr_source MATCHES "typedef struct zsock_fd_set UA_fd_set;")
    string(REPLACE "typedef struct zsock_fd_set UA_fd_set;"
        "typedef zsock_fd_set UA_fd_set;"
        open62541_zephyr_source "${open62541_zephyr_source}")
    file(WRITE "${open62541_zephyr_header}" "${open62541_zephyr_source}")
endif()

list(APPEND EXTRA_ZEPHYR_MODULES "${open62541_SOURCE_DIR}/arch")

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(osprey-app)

target_sources(app PRIVATE src/main.c src/server.c)
if(CONFIG_NATIVE_LIBC)
    # Keep event descriptors in Zephyr's fd table. The host eventfd() uses
    # different flag values and cannot be polled by zsock_select().
    target_compile_definitions(open62541-plugins PRIVATE
        eventfd=zvfs_eventfd
        eventfd_write=zvfs_eventfd_write
    )
endif()
if(CONFIG_NET_SOCKETS_OFFLOAD)
    # Zephyr omits getnameinfo.c with socket offloading, but open62541 needs it.
    target_sources(app PRIVATE "${ZEPHYR_BASE}/subsys/net/lib/sockets/getnameinfo.c")
endif()
target_link_libraries(app PRIVATE open62541)
