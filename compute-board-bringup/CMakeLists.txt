cmake_minimum_required(VERSION 3.28.0)

list(APPEND BOARD_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/..")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(compute_board_bringup)

target_sources(app PRIVATE
    src/main.c
    src/led.c
)