# Use the ordinary GNU C++ runtime for Zephyr targets. The SDK's `space`
# libstdc++ archive stubs exception state and breaks real C++ unwinding.
if(CONFIG_CPP AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  execute_process(
    COMMAND "${CMAKE_CXX_COMPILER}" ${TOOLCHAIN_C_FLAGS} -O2
            -print-file-name=libstdc++.a
    RESULT_VARIABLE _osprey_stdlib_query_status
    OUTPUT_VARIABLE _osprey_stdlib_archive
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  if(NOT _osprey_stdlib_query_status EQUAL 0 OR
     NOT EXISTS "${_osprey_stdlib_archive}")
    message(FATAL_ERROR
      "Unable to locate the non-space GNU libstdc++ runtime: "
      "${_osprey_stdlib_archive}")
  endif()

  # Zephyr freezes its compiler-driver link templates before application
  # CMakeLists are evaluated. Add a directory containing only the selected
  # archive, so this override cannot affect libc or libgcc selection.
  set(_osprey_stdlib_override_dir "${CMAKE_BINARY_DIR}/osprey-runtime")
  file(MAKE_DIRECTORY "${_osprey_stdlib_override_dir}")
  set(_osprey_stdlib_override "${_osprey_stdlib_override_dir}/libstdc++.a")
  if(IS_SYMLINK "${_osprey_stdlib_override}")
    file(READ_SYMLINK "${_osprey_stdlib_override}" _osprey_existing_stdlib)
  else()
    set(_osprey_existing_stdlib "")
  endif()
  if(NOT _osprey_existing_stdlib STREQUAL "${_osprey_stdlib_archive}")
    file(REMOVE "${_osprey_stdlib_override}")
    file(CREATE_LINK "${_osprey_stdlib_archive}"
         "${_osprey_stdlib_override}" SYMBOLIC)
  endif()
  target_link_options(zephyr_interface INTERFACE "-L${_osprey_stdlib_override_dir}")
  message(STATUS "Osprey C++ runtime: ${_osprey_stdlib_archive}")
endif()
