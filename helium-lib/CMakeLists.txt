# helium-lib: shared library code for the zeppelin workspace.
# Built as a Zephyr module library (see zephyr/module.yml).

zephyr_library()
file(GLOB app_sources src/*.c)
zephyr_library_sources(${app_sources})

if(CONFIG_OPEN62541)
    file(GLOB_RECURSE opcua_sources CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/src/opcua/*.c"
    )
    zephyr_library_sources(${opcua_sources})
    zephyr_library_link_libraries(open62541)
endif()

zephyr_include_directories(include)
