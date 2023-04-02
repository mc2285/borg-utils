import logging

import os
import subprocess
import tempfile
import util

import re

# Atomic wrapper for lvm snapshot


class BTRFSSnap:
    _snapshotNameRegex = re.compile(r'^[a-zA-Z0-9]+$')

    def __init__(self, sourcePath: str, name: str) -> None:
        self.__sourcePath = sourcePath
        self.__name = name
        self.__rootSubvol = None
        # Check if sourcePath is on a btrfs filesystem
        res = subprocess.run(
            ["stat", "-f", "-c", "%T", sourcePath], capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        if res.stdout.strip() != 'btrfs':
            raise ValueError(f"{sourcePath} is not on a btrfs filesystem")
        # Check if snapshot name is valid
        if not self._snapshotNameRegex.match(name):
            raise ValueError('Invalid snapshot name')
        # Determine root filesystem of sourcePath
        res = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE", "-T", sourcePath], capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        if "[" in res.stdout:
            self.__rootDevice = res.stdout.strip().split("[")[0].strip()
            self.__rootSubvol = res.stdout.strip().split("[")[1].strip("]")
        else:
            self.__rootDevice = res.stdout.strip()
        res = subprocess.run(
            ["findmnt", "-n", "-o", "TARGET", "-T", sourcePath], capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        self.__rootFS = res.stdout.strip()

    def __enter__(self):
        logging.info(
            f"Creating snapshot {self.__name} for {self.__sourcePath}")
        res = subprocess.run(
            ["btrfs", "subvolume", "snapshot", "-r",
             self.__sourcePath, f"{self.__rootFS}/{self.__name}"],
            capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        logging.info(
            f"Snapshot {self.__name} for {self.__sourcePath} created")
        # Now that the snapshot is created, make it's useful properties visible
        self.sourcePath = self.__sourcePath
        self.snapshotName = self.__name
        self.snapshotRootDevice = self.__rootDevice
        self.subvolPath = f"{self.__rootSubvol}/{self.__name}" if self.__rootSubvol else self.__name
        # The `with` statement expects the object to be returned
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        logging.info(
            f"Deleting snapshot {self.__name} for {self.__sourcePath}")
        res = subprocess.run(
            ["btrfs", "subvolume", "delete", f"{self.__rootFS}/{self.__name}"],
            capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        logging.info(
            f"Snapshot {self.__name} for {self.__sourcePath} deleted")
        return True if exc_type is None else False


class LVMSnap:
    _volumeNameRegex = re.compile(r'^[a-zA-Z0-9]+$')

    def __init__(self, volume: str, name: str, cowSize: int = None) -> None:
        self.__cowSize = cowSize
        if not self._volumeNameRegex.match(name):
            raise ValueError('Invalid snapshot name')
        logging.info(
            f"Checking if creating snapshot {name} for volume {volume} is possible")
        _args = ['lvcreate', '--name', name, '--snapshot', "--test", volume]
        if cowSize:
            _args.append(f"-L{cowSize}G")
        res = subprocess.run(_args, capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        logging.info(f"Snapshot {name} for volume {volume} is possible")
        self.__sourceVolume = volume
        self.__volumeGroup = volume.split('/')[-2]
        self.__snapshotName = name

    def __enter__(self):
        logging.info(
            f"Creating snapshot {self.__snapshotName} for volume {self.__sourceVolume}")
        _args = ['lvcreate', '--name', self.__snapshotName,
                 '--snapshot', self.__sourceVolume]
        if self.__cowSize:
            _args.append(f"-L{self.__cowSize}G")
        res = subprocess.run(_args, capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        # Force activation of the snapshot so that it can be mounted
        res = subprocess.run(
            ['lvchange', '-ay', '-y',
                f"{self.__volumeGroup}/{self.__snapshotName}"],
            capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        logging.info(
            f"Snapshot {self.__snapshotName} for volume {self.__sourceVolume} created")
        # Now that the snapshot is created, make it's properties visible
        self.sourceVolume = self.__sourceVolume
        self.volumeGroup = self.__volumeGroup
        self.snapshotName = self.__snapshotName
        self.cowSize = self.__cowSize
        # The `with` statement expects the object to be returned
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info(
            f"Deleting snapshot {self.__snapshotName} for volume {self.__sourceVolume}")
        res = subprocess.run(
            ['lvremove', '-f', f"{self.__volumeGroup}/{self.__snapshotName}"], capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        logging.info(
            f"Snapshot {self.__snapshotName} for volume {self.__sourceVolume} deleted")
        return True if exc_type is None else False


class Mount:
    def __init__(self, sourcePath, mountOptions: str = None) -> None:
        if not util.exists(sourcePath):
            raise FileNotFoundError(f"Device {sourcePath} does not exist")
        res = subprocess.run(
            ["lsblk", "-f", "-o", "FSTYPE", sourcePath], capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        self.fstype = res.stdout.splitlines()[-1].strip()
        self.__sourcePath = sourcePath
        self.sourcePath = sourcePath
        self.__mountOptions = mountOptions

    def __enter__(self):
        self.__mountpoint = tempfile.TemporaryDirectory()
        self.mountpoint = self.__mountpoint.name
        _mountOpts = "ro"
        if self.fstype == 'xfs':
            _mountOpts += ',nouuid'
        if self.__mountOptions:
            _mountOpts += f",{self.__mountOptions}"
        logging.info(
            f"Mounting {self.__sourcePath} to {self.__mountpoint.name}")
        logging.debug(f"mount -o {_mountOpts} {self.__sourcePath} {self.__mountpoint.name}")
        res = subprocess.run([
            'mount', "-o", _mountOpts,
            str(self.__sourcePath), self.__mountpoint.name
        ], capture_output=True, text=True)
        if res.returncode != 0:
            try:
                self.__mountpoint.cleanup()
            except:
                logging.warning(f"Failed to clean up {self.__mountpoint.name}")
            raise ChildProcessError(res.stderr)
        logging.info(
            f"Mounted {self.__sourcePath} to {self.__mountpoint.name}")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info(f"Unmounting {self.__mountpoint.name}")
        res = subprocess.run(
            ['umount', self.__mountpoint.name], capture_output=True, text=True)
        try:
            self.__mountpoint.cleanup()
        except:
            logging.warning(f"Failed to clean up {self.__mountpoint.name}")
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        logging.info(f"Unmounted {self.__mountpoint}")
        logging.info(f"Deleted {self.__mountpoint}")
        return True if exc_type is None else False
