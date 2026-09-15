# helium-lib: shared library code for the zeppelin workspace.
# Built as a Zephyr module library (see zephyr/module.yml).

zephyr_library()
file(GLOB app_sources src/*.c)
zephyr_library_sources(${app_sources})

zephyr_include_directories(include)
