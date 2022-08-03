# borg-utils

A collection of utilities for automated use of Borg on Linux

## What functionality does it bring?

Apart from simplifying creating both full and incremental backups by
automaticaly creating a subdirectory with a new Borg repo
if requested using `-c` (this is the equivalent of new full backup) and of course
archives in the currently latest Borg repo, the only cool thing it does
is the ability to automaticaly back up a live filesystem by facilitating
LVM snapshots, as long as it resides on an LVM volume that is (use the `--lvm` flag).

## Dependencies

- `python>=3.8`
- `python-systemd` (the pip package name is just `systemd`)

## Usage

Try:

```bash
python3 bkmgr.py --help
```

## How do I use it for scheduled backups?

I personaly recommend a combination of systemd timer(s) and systemd service(s).
It's simply easier to manage than Crontab.

Example:

(backup.service)
```ini
[Unit]
Requires=local-fs.target
[Service]
Type=simple
ExecStart=bash -c "exec /path/to/bkmgr/bkmgr.py --verbose --lvm /dev/vg0/my_lv_with_filesystem /path/to/backup/device"
Restart=on-failure
```

(backup.timer)
```ini
[Unit]
Description=Run incremental backup daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Remember to enable the timer:

```bash
sudo systemctl enable backup.timer && sudo systemctl start backup.timer
```

## Contributing

Feature ideas/requests are welcome. I made it to fit my needs,
if you need something more/else to fit yours, feel free to ask.
