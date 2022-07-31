#!/bin/python3

import argparse
import logging

import os
import subprocess

import util


def createRepo(path):
    path = os.path.abspath(path)
    logging.info(f"Validating the given path: {path}")
    if not util.exists(path):
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not util.accessible(path):
        raise PermissionError(f"User lacks required permissions: {path}")
    if not util.emptyDir(path):
        raise FileExistsError(
            f"Directory is not empty: {path} Refusing to proceed")
    logging.info(f"Creating Borg repo: {path}")
    res = subprocess.run(["borg", "init", "--encryption",
                         "none", str(path)], text=True, capture_output=True)
    if res.returncode == 1:
        logging.warn(res.stderr)
    elif res.returncode == 2:
        raise ChildProcessError(res.stderr)
    else:
        logging.info(f"Successfuly initialized unencrypted Borg repo: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize a Borg repository")
    parser.add_argument("path", metavar="DIR", nargs="+",
                        help="Directory to create the repository in")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    paths = args.path
    for path in paths:
        createRepo(path)
