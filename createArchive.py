#!/bin/python3

import argparse
import logging

import os
import subprocess

import util


def createArchive(archivePath, name: str, sourcePath):
    archivePath = os.path.abspath(archivePath)
    logging.info(f"Validating archive name: {name}")
    if "checkpoint" in name:
        raise ValueError(f"Archive name cannot contain `checkpoint`: {name}")
    if len(name) > 255 or len(name) < 1:
        raise ValueError(f"Archive name must be between 1 and 255 characters: {name}")
    logging.info(f"Validating the given path: {archivePath}")
    if not util.exists(archivePath):
        raise FileNotFoundError(f"Path does not exist: {archivePath}")
    if not util.writeable(archivePath):
        raise PermissionError(
            f"User lacks required permissions: {archivePath}")
    if util.emptyDir(archivePath):
        raise FileNotFoundError(
            f"Directory is empty: {archivePath}. Consider using createRepo.py first")
    logging.info(f"Validating source path: {sourcePath}")
    if not util.exists(sourcePath):
        raise FileNotFoundError(f"Path does not exist: {sourcePath}")
    if not util.readable(sourcePath):
        raise PermissionError(f"User lacks required permissions: {sourcePath}")
    logging.info(f"Creating Borg repo: {archivePath}")
    os.environ["BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK"] = "yes"
    res = subprocess.run(["borg", "create",
                          "--one-file-system", "--stats",
                          # The default of 30 minutes seems like an eternity to me
                          "--checkpoint-interval", "600",  # 600 seconds = 10 minutes
                          f"{archivePath}::{name}", str(sourcePath)], text=True, capture_output=True)
    if res.returncode == 1:
        logging.warn(res.stderr)
    elif res.returncode == 2:
        raise ChildProcessError(res.stderr)
    else:
        logging.info(f"Successfuly created archive: {archivePath}::{name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a Borg archive in an existing repository")
    parser.add_argument("archive", metavar="ARCHIVE",
                        help="Archive URI in format path::name")
    parser.add_argument("source", metavar="SRC",
                        help="Source directory to backup")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    try:
        archivePath, name = args.archive.split("::")
    except:
        raise ValueError(f"Invalid archive URI: {args.archive}")
    sourcePath = args.source
    createArchive(archivePath, name, sourcePath)
