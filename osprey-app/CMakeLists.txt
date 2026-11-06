cmake_minimum_required(VERSION 3.24)
cmake_policy(SET CMP0135 NEW) # Use extraction-time timestamps so dependency updates trigger rebuilds.

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BOARD nucleo_h723zg) # default board
set(UA_LOGLEVEL 400 CACHE STRING "open62541 minimum log level (400=WARNING)") # supress some of build log

include(FetchContent) # Populate sources before Zephyr discovers modules and their Kconfig options.
FetchContent_Declare(open62541
    URL https://codeload.github.com/open62541/open62541/tar.gz/47e704dcecf2505da263b02ebaaaf1d91ec6aae0
    URL_HASH SHA256=fe38fa4c1d7378dda6d46d1b2292ad568bc7d760298435a0846c596156725ab4
    SOURCE_SUBDIR arch/zephyr # Skip the root CMake project; Zephyr builds the library as a module.
)
FetchContent_MakeAvailable(open62541)

list(APPEND EXTRA_ZEPHYR_MODULES "${open62541_SOURCE_DIR}/arch")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(osprey-app)

target_compile_definitions_ifdef(CONFIG_NATIVE_LIBC open62541-plugins PRIVATE
    eventfd=zvfs_eventfd
    eventfd_write=zvfs_eventfd_write
) # Replace eventfds with zsock_select() for native_sim

target_sources_ifdef(CONFIG_NET_SOCKETS_OFFLOAD app PRIVATE
    "${ZEPHYR_BASE}/subsys/net/lib/sockets/getnameinfo.c"
) # Get getnameinfo.c because Zephyr omits it but open62541 needs it

file(GLOB app_sources src/*.c)
target_sources(app PRIVATE ${app_sources})
target_link_libraries(app PRIVATE open62541)
