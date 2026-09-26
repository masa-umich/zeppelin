option(OSPREY_SYNNAX_DTCM_HEAP "Place the CPU-only libc malloc arena in DTCM" OFF)
if(OSPREY_SYNNAX_DTCM_HEAP)
    if(NOT TARGET lib__libc__common)
        message(FATAL_ERROR "DTCM heap requires Zephyr's common libc malloc implementation")
    endif()
    # Override the arena annotation in this source only. This leaves the
    # system heap and Ethernet DMA buffers in SRAM and also works with LTO.
    set_property(SOURCE "${ZEPHYR_BASE}/lib/libc/common/source/stdlib/malloc.c"
        TARGET_DIRECTORY lib__libc__common APPEND PROPERTY COMPILE_OPTIONS
        -include "${CMAKE_CURRENT_LIST_DIR}/../port/include/dtcm_malloc.h")
endif()
