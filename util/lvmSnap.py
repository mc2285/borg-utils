import logging

import subprocess
import tempfile
import util

import re

# Atomic wrapper for lvm snapshot


class Snap:
    _volumeNameRegex = re.compile(r'^[a-zA-Z0-9]+$')

    def __init__(self, volume: str, name: str, cowSize: None) -> None:
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
    def __init__(self, sourcePath) -> None:
        if not util.exists(sourcePath):
            raise FileNotFoundError(f"Device {sourcePath} does not exist")
        res = subprocess.run(
            ["lsblk", "-f", "-o", "FSTYPE", sourcePath], capture_output=True, text=True)
        if res.returncode != 0:
            raise ChildProcessError(res.stderr)
        self.fstype = res.stdout.splitlines()[-1].strip()
        self.__sourcePath = sourcePath
        self.sourcePath = sourcePath

    def __enter__(self):
        self.__mountpoint = tempfile.TemporaryDirectory()
        self.mountpoint = self.__mountpoint.name
        _mountOpts = "ro"
        if self.fstype == 'xfs':
            _mountOpts += ',nouuid'
        logging.info(
            f"Mounting {self.__sourcePath} to {self.__mountpoint.name}")
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
