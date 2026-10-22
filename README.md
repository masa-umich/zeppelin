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
just build kestrel-app
```
> [!NOTE]
> You will need to build at least once before your editor will pick up on the libraries
> and intellisense.

This repository can also be used with the VSCode extension [*Workbench for Zephyr*](https://marketplace.visualstudio.com/items?itemName=Ac6.zephyr-workbench). After following the previous steps, open the `Zeppelin.code_workspace` file to open the configured workspace.

## Development

### Build, Run, Test for Board Target
1. Build app for target:
```bash
just build kestrel-app
```
2. Flash app to target
```bash
just flash kestrel-app
```
3. If relevant, use your favorite serial terminal to connect to the board. (just command alias comming soon)

## Simulation
Simulation is currently handled by using the `native_sim` target inside of a [podman container](https://podman.io/). The reason this cannot be done natively is because `native_sim` requires a Linux machine to run on which is obviously not cross platform. Podman also allows more deterministic builds and network bridging.

### Installation
Simulation installation depends on your opperating system. The only dependency is Podman, everything else will be automatically downloaded as part of the container. You also must have already initialized the Zephyr workspace for this to work as it relies on mounting your existing directory.

<details>
    <summary>Windows</summary>

Run in Administrator PowerShell, then restart Windows if prompted:

```powershell
wsl --install --no-distribution
winget install --exact --id Podman.CLI
```

Open a new PowerShell terminal:

```powershell
podman machine init
podman machine start
podman run --rm docker.io/library/hello-world
```

</details>

<details>
    <summary>macOS</summary>

With [Homebrew](https://brew.sh) installed:

```bash
brew install podman
podman machine init
podman machine start
podman run --rm docker.io/library/hello-world
```

</details>

<details>
    <summary>Linux</summary>

On Debian/Ubuntu (other distributions: [Podman installation](https://podman.io/docs/installation)):

```bash
sudo apt-get update
sudo apt-get install -y podman
podman run --rm docker.io/library/hello-world
```

</details>

On macOS and Windows, run `podman machine start` after rebooting; `podman machine init` is only needed once.

### Running the Simulation
Running a simulation should be as easy as this:
```bash
just sim build <target>
just sim run <target>
```

In the rare event where you need to run something inside the Podman container manually, you can also run generic commands inside the container like this:
```bash
just sim container '<command>'
```

## Troubleshooting

Below are some common issues you might run into, but if you can't find what you need, remember you can always ask in [#av_nostupidquestions](https://masaumich.slack.com/archives/C06RKGKKT6D)!

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

<details>
    <summary>Updating your branch with changes from main</summary>

This isn't really a Zeppelin specific issue, but one I wanted to cover in this README because it's something you'll probably run into.

If you're working on a branch and there are new changes in main that you want to add to your branch, you should use this command pattern:
```bash
git fetch origin
git rebase origin/main
git push --force-with-lease origin HEAD
```
This will fetch changes from main, rebase the timeline so that they're applied retroactively before you made any changes, then push that new timeline onto your branch. This is such a common pattern I made a Git alias which you can copy like this:
```bash
git config --global alias.rebase-push '!git fetch origin && git rebase origin/main && git push --force-with-lease origin HEAD'
```
Then updating your branch becomes as easy as running:
```bash
git rebase-push
```
The only caveat with doing things this way is that it can have merge conflicts if the changes from main interfere with changes you've made on your branch, in which case I reccomend getting an LLM to help you fix the situation.
</details>
