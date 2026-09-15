# Zeppelin project automation
# Mostly exists to not have to activate the python venv by wrapping `uv run`
set ignore-comments := true

# just selects the platform's shell and resolves its executable automatically.
# Windows uses built-in Windows PowerShell; Git Bash is not required.
set shell := ["sh", "-cu"]
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]

[private] # private so it doesn't show itself in the list
default:
    @just --list

# Generic west wrapper
west *ARGS:
    uv run west {{ARGS}}

# clang-format check of all source files (dryrun)
[unix]
check:
    git add .
    git ls-files "*.cpp" "*.h" "*.hpp" "*.cc" "*.c" | xargs uv run clang-format --dry-run --Werror -style=file || true
    # use clang-format from uv venv and finds files using git which should be guarenteed to exist

# clang-format all source files
[unix]
format:
    git add .
    git ls-files "*.cpp" "*.h" "*.hpp" "*.cc" "*.c" | xargs uv run clang-format -i -style=file || true

# Windows equivalents: no xargs dependency or PowerShell 7-only || operator.
# As above, clang-format failures are reported but do not fail the recipe.
[windows]
check:
    git add .
    git ls-files "*.cpp" "*.h" "*.hpp" "*.cc" "*.c" | ForEach-Object { uv run clang-format --dry-run --Werror -style=file -- $_ }; exit 0

[windows]
format:
    git add .
    git ls-files "*.cpp" "*.h" "*.hpp" "*.cc" "*.c" | ForEach-Object { uv run clang-format -i -style=file -- $_ }; exit 0

# First time setup
setup:
    @echo "{{YELLOW}}{{BOLD}}Running first time setup...{{NORMAL}}"
    # NOTE: Python 3.13+ will break setup because of changes to filesystem paths
    uv venv --python 3.12 --clear
    uv pip install pip west jsonschema
    just update

# Auto-update west and Zephyr dependencies
update:
    @echo "{{BLUE}}Checking for updates...{{NORMAL}}"
    git fetch
    uv run west update
    uv run west packages-uv uv --install
    uv run west sdk install
    uv run west zephyr-export
    uv run west blobs fetch hal_espressif

# Flash the connected board
flash:
    uv run west flash

default_baud := "115200"

# Open a serial console (default baud 115200)
console baud=default_baud:
    @echo "{{BLUE}}Starting serial console with baud rate: {{GREEN}}{{baud}}{{NORMAL}}"
    uv run west espressif monitor
    # TODO: make into generic serial monitor with something like minicom

# Run (and build if needed) the native_sim build
[unix]
run-sim: (build "akron-app" "true")
    @echo "{{BLUE}}Running native_sim...{{NORMAL}}"
    ./build/zephyr/zephyr.exe

# Build a target (pass --sim to build for native_sim)
[arg("sim", long, value="true")]
build target sim="false":
    @echo "{{BLUE}}Building{{NORMAL}} {{target}}..."
    uv run west build {{target}} -p auto -b {{ if sim == "true" { "native_sim" } else { "esp32_devkitc/esp32/procpu" } }}
