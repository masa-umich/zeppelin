import argparse
import os
import shutil
from pathlib import Path

DIRS_TO_RM = [".cache", "build"]
IGNORED_DIRS = [".git", ".venv", ".cache", "build"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default="")
    args = parser.parse_args()

    root = Path(args.directory or ".")
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    def fail(error):
        raise error

    directories = os.walk(root, onerror=fail) if not args.directory else [(root, [], [])]
    for current, subdirs, _ in directories:
        subdirs[:] = [
            name for name in subdirs
            if name not in IGNORED_DIRS
            and not (Path(current) / name).is_junction()
        ]
        for name in DIRS_TO_RM:
            path = Path(current) / name
            if path.is_dir() and not path.is_symlink() and not path.is_junction():
                shutil.rmtree(path)
                print(f"Removed {path}")


if __name__ == "__main__":
    main()
