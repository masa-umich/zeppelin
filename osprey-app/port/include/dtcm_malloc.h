/*
 * Preincluded only when OSPREY_SYNNAX_DTCM_HEAP is enabled. Zephyr's common
 * malloc implementation uses __noinit for its arena when userspace is off;
 * redirect that one arena to the board's linker-defined DTCM noinit section.
 */
#pragma once

#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/linker/section_tags.h>

#if defined(CONFIG_USERSPACE)
#error "The Osprey DTCM malloc arena override requires CONFIG_USERSPACE=n"
#endif

#if !DT_NODE_EXISTS(DT_CHOSEN(zephyr_dtcm))
#error "The Osprey DTCM malloc arena override requires chosen zephyr,dtcm"
#endif

BUILD_ASSERT(CONFIG_COMMON_LIBC_MALLOC_ARENA_SIZE > 0,
             "The Osprey DTCM malloc arena override requires a static malloc arena");
BUILD_ASSERT(CONFIG_COMMON_LIBC_MALLOC_ARENA_SIZE <=
                 DT_REG_SIZE(DT_CHOSEN(zephyr_dtcm)),
             "The Osprey libc malloc arena is larger than chosen DTCM");

#undef __noinit
#define __noinit __dtcm_noinit_section
