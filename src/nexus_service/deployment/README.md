# Running the acquisition service as a system daemon

The `nexus` service can run as a systemd unit that is started at boot and shared by every
account on the workstation. All steps below change the system and require root; none of them
is performed by the package itself. Without them, `nexus -d <config>` started by hand keeps
working as described in the user guide (runtime directory `<tempdir>/nexus`).

## 1. Service account

To run the daemon we use an unprivileged system account which can be created by:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --comment "Nexus acquisition service" nexus
```

| Part                                    | Meaning                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------- |
| `useradd`                               | Linux command for creating a user account.                                                  |
| `--system`                              | Create a **system account**, intended for services/daemons rather than a normal human user. |
| `--no-create-home`                      | Don't create a home directory such as `/home/nexus`.                                        |
| `--shell /usr/sbin/nologin`             | Set the user's login shell to `nologin`, preventing interactive shell logins.               |
| `--comment "Nexus acquisition service"` | Add descriptive information to the account's comment field.                                 |
| `nexus`                                 | The username being created.                                                                 |


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
