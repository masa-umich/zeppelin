cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(osprey_runtime_port_tests LANGUAGES C CXX)

include("${CMAKE_CURRENT_SOURCE_DIR}/../../port/runtime.cmake")

zephyr_compile_definitions(_XOPEN_SOURCE=700)
zephyr_compile_definitions(NDEBUG=1)
zephyr_compile_definitions($<$<COMPILE_LANGUAGE:CXX>:_GLIBCXX_HAS_GTHREADS=1>)
zephyr_compile_definitions($<$<COMPILE_LANGUAGE:CXX>:_GLIBCXX_HAVE_TLS=1>)
zephyr_include_directories("${CMAKE_CURRENT_SOURCE_DIR}/../../port/include")

target_sources(app PRIVATE
    src/main.cpp
    "${CMAKE_CURRENT_SOURCE_DIR}/../../port/std_thread.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../src/atomic64.cpp")
