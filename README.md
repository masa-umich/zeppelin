# Zeppelin

MASA's board firmware made with Zephyr

This repo is setup as a T2 "star topology" meaning the apps are in the same repository as the manifest file. This means you should not clone this repo directly; instead, you should use `west` to clone it into a "west workspace" directory.

## Setup
1. Install System Package Dependencies (OS specific instructions linked below)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Zephyr System Package Dependencies](https://docs.zephyrproject.org/latest/develop/getting_started/index.html#install-dependencies)
2. Clone this repo
```bash
uvx west init -m https://github.com/masa-umich/zeppelin.git --mr main zeppelin-workspace
cd zeppelin-workspace/zeppelin
```
3. Install the [just](https://just.systems/man/en/) command runner and run the setup command
```bash
uv tool install rust-just
just setup
```
> [!NOTE]
> This may take a while and use quite a bit of space (~3.5GB)!
4. Try to build a project to confirm setup works:
```bash
just build akron-app
```
> [!NOTE]
> You will need to build at least once before your editor will pick up on the libraries
> and intellisense.

This repository can also be used with the VSCode extension [*Workbench for Zephyr*](https://marketplace.visualstudio.com/items?itemName=Ac6.zephyr-workbench). After following the previous steps, open the `Zeppelin.code_workspace` file to open the configured workspace.

## Development

### Build, Run, Test for Board Target
1. Build app for target:
```bash
just build akron-app
```
2. Flash app to target
```bash
just flash
```
3. Open a serial terminal to target
```bash
just console # command alias is work in progress
```
### Build, Run, Test for Simulation (POSIX only)
> [!IMPORTANT]
> This can only work on a POSIX system (Linux), if using Windows you must use WSL, or MacOS must use a VM.
1. Build app, but with `--sim` flag
```bash
just build akron-app --sim
```
2. Run app
```bash
just run-sim
```
As the simulation capabilities of this project expand there may be more requirements and libraries but for now this is it!

### Useful Commands & Workflow
In general, run `just` (no arguments) to get a list of recipes that can be ran:
```bash
Available recipes:
    build [OPTIONS] target    # Build a target (pass --sim to build for native_sim)
    check                     # clang-format check of all source files (dryrun)
    console baud=default_baud # Open a serial console (default baud 115200)
    flash                     # Flash the connected board
    format                    # clang-format all source files
    run-sim                   # Run (and build if needed) the native_sim build
    setup                     # First time setup
    update                    # Auto-update west and Zephyr dependencies
    west *ARGS                # Generic west wrapper
```
Most of these are straightforward but some to take note of are:
- `just format`: Runs `clang-format` over all source files. If making a pull request, all source files should meet this spec.
- `just update`: Ensures that depencies are installed and update for Zephyr, modules, west packages, cmake variables, and blobs.
- `just west <args>`: A generic wrapper for west commands. Useful if you don't want to activate the venv to run a command.

## Troubleshooting

<details>
    <summary>Flashing on Linux permission fails</summary>

If `west flash` does not work and you are on Linux, you may need to add your user to the `dialout` group:
```bash
sudo usermod -a -G dialout $USER
```
And then logout entirely (or reboot) and log back in.
</details>

<details>
    <summary>Build failing after pulling new changes</summary>

If your builds are suddenly failing and they weren't before after pulling new changes, it's possible a new dependency was added to the project which has not yet been installed locally. It's a good idea to run the update command after every pull in case there are changes:
```bash
just update
```
It's possible that dependencies will be added to the project but not to the justfile, in which case shame on me! But I will try to keep it up-to-date.
</details>

<details>
    <summary>The setup fails because there is "no workspace"</summary>

This might happen if you don't follow step 2 of the guide exactly. If you try to use `git clone` it will not work because this repository needs to exist in another directory called your "workspace" and even if you make a dedicated directory and then try to use `git clone`, it will still fail because west needs to find a `.west` directory (which is auto-generated when using `west init`). 

So TLDR: just use the exact `uvx west init ...` command from above.
</details>
