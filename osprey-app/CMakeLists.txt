cmake_minimum_required(VERSION 3.20.0)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BOARD nucleo_h723zg) # default board

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(osprey-app)

target_sources(app PRIVATE src/main.c)
