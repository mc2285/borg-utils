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
    if not util.writeable(path):
        raise PermissionError(f"User lacks required permissions: {path}")
    if not util.emptyDir(path):
        raise FileExistsError(
            f"Directory is not empty: {path} Refusing to proceed")
    logging.info(f"Creating Borg repo: {path}")
    """
        Why no encryption? Encryption at rest schould be handled by the storage provider.
        There is no need to encrypt multiple times as it increases the risk of data loss,
        overhead and complexity of the system. Backups are meant to decrease the risk
        of data loss, not to create it. Also please mind, that `borg init --encryption=authenticated`
        can also render the backup useless in case the config file and/or key is lost.
        See https://github.com/borgbackup/borg/issues/6916 and
        https://github.com/borgbackup/borg/issues/4042
    """
    res = subprocess.run(["borg", "init", "--encryption",
                         "none", str(path)], text=True, capture_output=True)
    if res.returncode == 1:
        logging.warning(res.stderr)
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
