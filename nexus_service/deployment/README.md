# Running the acquisition service as a system daemon

The `nexus` service can run as a systemd unit that is started at boot and shared by every
account on the workstation. All steps below change the system and require root; none of them
is performed by the package itself. Without them, `nexus -d <config>` started by hand keeps
working as described in the user guide (runtime directory `<tempdir>/nexus`).

## 1. Service account

The daemon must run as some account. Do not use root: a client holding the authentication key
(readable by every account) can make the service execute code on its behalf, so a root service
would hand root to every user of the workstation. Do not use a personal account either: the
service would depend on that person's home, password and account lifetime, and clients could
act with that person's rights. Create an unprivileged system account instead:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --comment "Nexus acquisition service" nexus
```

`--system` takes a UID from the system range and creates neither mail spool nor password
aging, no password is set so nobody can log in, `nologin` rejects shells, and there is no home
directory (the unit sets `HOME` to the state directory). The account is not a member of any
other group and has no sudo rights. It can open the measurement cards because
`/dev/spcm*` are world-accessible (`MODE="0666"` in `/etc/udev/rules.d/99-spcm4.rules`).

## 2. Installation

Install the package into a virtual environment the account can read, for example
`/opt/nexus/venv`, and place the device configuration at `/etc/nexus/device_config.yaml`.
Adapt both paths in `ExecStart` of `nexus.service` if you choose different ones.

```bash
sudo cp nexus_service/deployment/nexus.service /etc/systemd/system/nexus.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexus
```

The unit starts with `--no-verify` because there is no terminal to confirm that the
amplifiers are off, and with `--sessions_folder /var/lib/nexus` because the account has no home.

## 3. What systemd does

On start systemd creates `/run/nexus` (`RuntimeDirectory=`, owner `nexus`, mode `0755`) and
`/var/lib/nexus` (`StateDirectory=`), then drops to the `nexus` account. The service publishes
`nexus.sock` (`0666`) and `authkey` (`0644`) in `/run/nexus`, which the clients find
automatically. On stop, and after a crash, systemd removes `/run/nexus` again, so no stale
socket or key survives. `/run` is owned by root, therefore only root can delete the directory
and no other account can place files in it. Do not add `PrivateTmp=yes` to the unit: it is
harmless with `/run/nexus`, but would hide the `<tempdir>/nexus` fallback from the clients.

## 4. Usage

Any account connects without arguments, the examples are unchanged:

```python
with AcquisitionControlManager() as manager:
    ...
```

Starting and stopping the unit requires root: `sudo systemctl start nexus`,
`sudo systemctl stop nexus`, `journalctl -u nexus` shows the service output.
