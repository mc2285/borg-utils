#!/usr/bin/env python3

import argparse
import logging

import io
import os
import time
import uuid

import util
import util.handlers as handlers
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
    parser.add_argument("--cow-size", metavar="COW_SIZE", type=int,
                        help="Specify the size for a COW snapshot in GiB. " +
                        "Defaults to 64GiB. Valid on both classic and thin " +
                        "LVM volumes")
    parser.add_argument("-n", "--no-cow", action="store_true",
                        help="Use LVM thin snapshots instead of COW snapshots. " +
                        "Valid only in on thin LVM volumes")
    parser.add_argument("-c", "--create-repo",
                        action="store_true",
                        help="Create a new repo and update lockfile")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()
    # Register systemd journal as logging handler
    if args.debug:
        logging.root.setLevel(logging.DEBUG)
    elif args.verbose:
        logging.root.setLevel(logging.INFO)
    else:
        logging.root.setLevel(logging.WARNING)
    # Gracefuly exit on unhandled exceptions
    try:
        # Validate arguments for conflicting options and invalid values
        if not args.lvm and (args.cow_size or args.no_cow):
            # cow_size is meaningless if lvm is not set so the default doesn't matter
            raise ValueError(
                "'COW Size' and 'No Cow' options are only valid when using LVM as backend")
        elif args.cow_size and args.no_cow:
            raise ValueError(
                "'COW Size' and 'No Cow' options are mutually exclusive")
        # Assign a default to cow_size if it's not set
        if not args.cow_size:
            args.cow_size = 64
        elif args.cow_size <= 0:
            raise ValueError("'COW Size' must be greater than 0")
        # Unset cow_size if no_cow is set
        if args.no_cow:
            args.cow_size = None

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
        if not util.exists(repoPath):
            raise FileNotFoundError(f"Path does not exist: {repoPath}")
        if not util.exists(args.source):
            raise FileNotFoundError(f"Path does not exist: {args.source}")
        if args.lvm:
            with lockFileHandle:
                snaphotHandle = handlers.LVMSnap(
                    args.source, "bkmgrsnap" + uuid.uuid4().hex, args.cow_size)
                with snaphotHandle:
                    mountpointHandle = handlers.Mount(
                        os.path.join(
                            os.path.sep, "dev",
                            snaphotHandle.volumeGroup, snaphotHandle.snapshotName
                        )
                    )
                    with mountpointHandle:
                        makeBackup(repoPath, mountpointHandle.mountpoint)
        else:
            with lockFileHandle:
                # Check if BTRFS snapshot is available
                try:
                    snaphotHandle = handlers.BTRFSSnap(
                        args.source, "bkmgrsnap" + uuid.uuid4().hex)
                except (ValueError, ChildProcessError) as ex:
                    logging.info("BTRFS snapshot not available:")
                    logging.info(f"\t{str(ex)}")
                    makeBackup(repoPath, args.source)
                else:
                    with snaphotHandle:
                        mountpointHandle = handlers.Mount(
                            snaphotHandle.snapshotRootDevice,
                            f"subvol={snaphotHandle.subvolPath}"
                            )
                        with mountpointHandle:
                            makeBackup(repoPath, mountpointHandle.mountpoint)
        logging.info("Backup complete")
    except BaseException:
        logging.exception("An unhandled exception has occurred:")
        logging.critical("Backup failed. Exiting on error...")
        exit(1)
