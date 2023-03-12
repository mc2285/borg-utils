#!/usr/bin/env python3

import argparse
import logging

import io
import os
import time
import uuid

import util
import util.lvmSnap as lvmSnap
import createArchive
import createRepo

APP_DESCRIPTION = "Borg Backup Manager"


def makeBackup(repoPath: str, sourcePath: str):
    createArchive.createArchive(
        repoPath, r"{hostname}-{now}", sourcePath)


def makeRepo(rootPath, lockFilePath):
    path = time.strftime(r"%Y-%m-%d_%H:%M:%S")
    logging.info(f"Creating new repo directory: {path}")
    repoPath = os.path.join(rootPath, path)
    os.mkdir(repoPath)
    createRepo.createRepo(repoPath)
    with open(lockFilePath, "w") as f:
        f.write(path)
        f.write(os.linesep)
    logging.info("Lock file updated")


def getCurrentRepoHandle(basePath, handlePath: str) -> io.TextIOWrapper:
    if not util.exists(handlePath):
        raise FileNotFoundError(f"Path does not exist: {handlePath}")
    if not util.readable(handlePath) or not util.fileWriteable(handlePath):
        raise PermissionError(f"User lacks required permissions: {handlePath}")
    return open(handlePath, "r+")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=APP_DESCRIPTION)
    parser.add_argument("source", metavar="SRC",
                        help="Source directory containing data to backup")
    parser.add_argument("target", metavar="TARGET",
                        help="Root directory the archives reside in")
    parser.add_argument("-l", "--lvm", action="store_true",
                        help="Use LVM snapshots to backup a filesystem on LVM volume")
    parser.add_argument("-c", "--create-repo",
                        action="store_true",
                        help="Create a new repo and update lockfile")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")
    args = parser.parse_args()
    # Register systemd journal as logging handler
    if args.verbose:
        logging.root.setLevel(logging.INFO)
    else:
        logging.root.setLevel(logging.WARNING)
    # Gracefuly exit on unhandled exceptions
    try:
        lockFilePath = os.path.join(args.target, "lock.txt")
        # Create new repo if requested
        if args.create_repo:
            makeRepo(args.target, lockFilePath)
        try:
            lockFileHandle = getCurrentRepoHandle(args.target, lockFilePath)
        except FileNotFoundError:
            # If the lock file doesn't exist, create it
            makeRepo(args.target, lockFilePath)
            lockFileHandle = getCurrentRepoHandle(args.target, lockFilePath)
        repoPath = os.path.join(args.target, lockFileHandle.read().strip())
        if args.lvm:
            with lockFileHandle:
                if not util.exists(repoPath):
                    raise FileNotFoundError(f"Path does not exist: {repoPath}")
                snaphotHandle = lvmSnap.Snap(
                    args.source, "bkmgrsnap" + uuid.uuid4().hex)
                with snaphotHandle:
                    mountpointHandle = lvmSnap.Mount(
                        os.path.join(
                            os.path.sep, "dev",
                            snaphotHandle.volumeGroup, snaphotHandle.snapshotName
                        )
                    )
                    with mountpointHandle:
                        makeBackup(repoPath, mountpointHandle.mountpoint)
        else:
            with lockFileHandle:
                makeBackup(repoPath, args.source)
        logging.info("Backup complete")
    except BaseException:
        logging.exception("An unhandled exception has occurred:")
        logging.critical("Backup failed. Exiting on error...")
        exit(1)
