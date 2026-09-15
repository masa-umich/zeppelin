"""
Zephyr's `west packages` command with added `uv` support, exposed as the
`west packages-uv` command.

This is based on the upstream PR
https://github.com/zephyrproject-rtos/zephyr/pull/94432 which was never
merged. Instead of vendoring the whole command, we subclass the upstream
``Packages`` class and only add the ``uv`` sub-command, so we keep tracking
upstream fixes to the rest of the command.

We register this under the distinct name ``packages-uv`` rather than
shadowing Zephyr's ``packages`` command, to avoid the "already defined as
extension command" warning west emits for duplicate command names.

Credit: Claude Opus 4.8
"""

import argparse
import os
import subprocess
import sys
import textwrap
from itertools import chain
from pathlib import Path

# Make Zephyr's west_commands (packages.py) and scripts/ importable so we can
# subclass the upstream command and reuse its helpers.
#
# Prefer the ZEPHYR_BASE environment variable (set by `zephyr-env.sh` /
# `zephyr-env.cmd`). Fall back to locating the zephyr project relative to this
# file within the west workspace.
def _find_zephyr_base() -> Path:
    env = os.environ.get("ZEPHYR_BASE")
    if env and Path(env).is_dir():
        return Path(env)

    # This file lives at <workspace>/zeppelin/scripts/west_commands/packages_uv.py
    # so the workspace topdir is parents[3] and zephyr is a sibling of zeppelin.
    candidate = Path(__file__).resolve().parents[3] / "zephyr"
    if candidate.is_dir():
        return candidate

    raise RuntimeError(
        "Could not locate the Zephyr base directory. "
        "Set the ZEPHYR_BASE environment variable and retry."
    )


_ZEPHYR_BASE_DIR = _find_zephyr_base()
_ZEPHYR_WEST_COMMANDS = _ZEPHYR_BASE_DIR / "scripts" / "west_commands"
_ZEPHYR_SCRIPTS = _ZEPHYR_BASE_DIR / "scripts"
for _p in (_ZEPHYR_WEST_COMMANDS, _ZEPHYR_SCRIPTS):
    if _p.is_dir() and os.fspath(_p) not in sys.path:
        sys.path.append(os.fspath(_p))

from packages import Packages as _ZephyrPackages  # noqa: E402
from packages import in_venv  # noqa: E402
from zephyr_ext_common import ZEPHYR_BASE  # noqa: E402


class Packages(_ZephyrPackages):
    def __init__(self):
        # Register under a distinct name (``packages-uv``) instead of the
        # upstream ``packages`` name. West rebuilds a fresh parser at
        # invocation time and registers the command's subparser using
        # ``self.name`` (see west.app.main.run_extension /
        # WestCommand.add_parser). If we inherited the upstream ``packages``
        # name, west would look up the invoked ``packages-uv`` command name
        # against a subparser registered as ``packages`` and fail with
        # "invalid choice: 'packages-uv'". Setting the name here keeps the
        # command name, its stub parser, and its real parser consistent.
        #
        # We intentionally do NOT call the parent __init__ (which hardcodes
        # the "packages" name); we call the grandparent WestCommand.__init__
        # directly with our own name.
        super(_ZephyrPackages, self).__init__(
            "packages-uv",
            "manage packages for Zephyr (with uv support)",
            "List and Install packages for Zephyr and modules, with uv support",
            accepts_unknown_args=True,
        )

    def do_add_parser(self, parser_adder):
        # Let upstream build the base parser (including the `pip` sub-parser and
        # the shared `-m/--module` option). We then reach into its subparsers
        # action to register our extra `uv` sub-command.
        parser = super().do_add_parser(parser_adder)

        # Find the manager subparsers action created by the parent.
        subparsers_gen = next(
            a for a in parser._subparsers._group_actions
            if isinstance(a, argparse._SubParsersAction)
        )

        uv_parser = subparsers_gen.add_parser(
            "uv",
            help="manage uv packages",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent(
                """
            Manage uv packages:

                Run 'west packages-uv uv' to print all requirement files needed by
                Zephyr and modules.

                The output is compatible with the requirements file format itself.
            """
            ),
        )

        uv_parser.add_argument(
            "--install",
            action="store_true",
            help="Install uv requirements instead of listing them. "
            "A single 'uv pip install' command is built and executed. "
            "Additional uv arguments can be passed after a -- separator "
            "from the original 'west packages-uv uv --install' command. For example pass "
            "'--dry-run' to uv not to actually install anything, but print what would be.",
        )

        uv_parser.add_argument(
            "--ignore-venv-check",
            action="store_true",
            help="Ignore the virtual environment check. "
            "This is useful when running 'west packages-uv uv --install' "
            "in a CI environment where the virtual environment is not set up.",
        )

        return parser

    def do_run(self, args, unknown):
        if args.manager == "uv":
            if len(unknown) > 0 and unknown[0] != "--":
                self.die(
                    f'Unknown argument "{unknown[0]}"; '
                    'arguments for the manager should be passed after "--"'
                )

            import zephyr_module

            self.zephyr_modules = zephyr_module.parse_modules(ZEPHYR_BASE, self.manifest)

            if args.modules:
                module_names = [m.meta.get("name") for m in self.zephyr_modules]
                module_names.append("zephyr")
                for m in args.modules:
                    if m not in module_names:
                        self.die(f'Unknown zephyr module "{m}"')

            return self.do_run_uv(args, unknown[1:])

        # Anything else (e.g. `pip`) is handled by the upstream implementation.
        return super().do_run(args, unknown)

    def do_run_uv(self, args, manager_args):
        requirements = []

        if not args.modules or "zephyr" in args.modules:
            requirements.append(ZEPHYR_BASE / "scripts/requirements.txt")

        for module in self.zephyr_modules:
            module_name = module.meta.get("name")
            if args.modules and module_name not in args.modules:
                if args.install:
                    self.dbg(f"Skipping module {module_name}")
                continue

            # Get the optional pip section from the package managers,
            # uv is compatible with pip.
            pip = module.meta.get("package-managers", {}).get("pip")
            if pip is None:
                if args.install:
                    self.dbg(f"Nothing to install for {module_name}")
                continue

            # Add requirements files
            requirements += [Path(module.project) / r for r in pip.get("requirement-files", [])]

        if args.install:
            if not in_venv() and not args.ignore_venv_check:
                self.die("Running uv pip install outside of a virtual environment")

            if len(requirements) > 0:
                subprocess.check_call(
                    ["uv", "pip", "install"]
                    + list(chain.from_iterable([("-r", r) for r in requirements]))
                    + manager_args
                )
            else:
                self.inf("Nothing to install")
            return

        if len(manager_args) > 0:
            self.die(f'west packages-uv uv does not support unknown arguments: "{manager_args}"')

        self.inf("\n".join([f"-r {r}" for r in requirements]))
