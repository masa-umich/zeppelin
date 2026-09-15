cmake_minimum_required(VERSION 3.20.0)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BOARD esp32_devkitc/esp32/procpu) # default board

# Pull in the sibling helium-lib as an out-of-tree Zephyr module
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/../helium-lib)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(akron-app)

file(GLOB app_sources src/*.c)
target_sources(app PRIVATE ${app_sources})
