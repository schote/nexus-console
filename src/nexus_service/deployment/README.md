# Deployment: Running the acquisition service as a system daemon

The `nexus` service can run as a systemd unit that is started at boot and shared by every
account on the workstation. All steps below change the system and require root; none of them
is performed by the package itself. Without them, `nexus -d <config>` started by hand keeps
working as described in the user guide (runtime directory `<tempdir>/nexus`).

```mermaid
%%{init: {
  "themeVariables": {
    "fontFamily": "Inter, Segoe UI, Helvetica Neue, Arial, sans-serif",
    "fontSize": "14px"
  },
  "flowchart": {
    "curve": "basis",
    "nodeSpacing": 40,
    "rankSpacing": 80,
    "padding": 12
  }
}}%%
flowchart LR
    systemd("`**systemd**
    /etc/systemd/system/nexus.service
    *runs as root*`")
    service("`**nexus service**
    /opt/nexus/venv/bin/nexus
    *runs as nexus*`")
    user("`**user**
    AcquisitionControlManager()
    *any account*`")
    run("`**runtime directory**
    /run/nexus
    contains nexus.sock & authkey
    *owned by nexus*`")
    logs("`**log directory**
    /var/log/nexus
    contains one log file per day
    *owned by nexus*`")

    systemd -- "creates /run/nexus and /var/log/nexus, starts" --> service
    service -- "publishes socket and key" --> run
    service -- "writes log files" --> logs
    run <-- "connects via socket, authenticates with key" --> user

    classDef actor fill:#e6fbf6,stroke:#2ec4a5,stroke-width:2px,color:#1e293b,rx:10px,ry:10px
    classDef location fill:#fff1e6,stroke:#f5a05a,stroke-width:2px,color:#1e293b,rx:10px,ry:10px
    class systemd,service,user actor
    class run,logs location
```

*Figure: deployment overview. Teal boxes are actors, orange boxes are locations on disk. The
log directory is not accessed by `AcquisitionControlManager`; users inspect it manually.
The service stores no acquisition data, see [Acquisition data](#acquisition-data) below.
The permission modes used in the steps below mean the following:
`755`: the owner (`nexus`) may create and delete entries, everyone else may only list and enter
the directory. `666`: everyone may read and write; for a socket, "write" is what a `connect()`
requires, so any account can reach the service. `644`: everyone may read, only the owner (`nexus`)
may write, so clients can fetch the key and the log files but not alter them.*

## 1. Create a service account

To run the daemon, we use an unprivileged system account, which can be created with:

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

It is suggested to use the `/opt` directory, which is reserved for add-on application software packages, and to install the console application in a virtual environment.
Create a virtual environment, copy the code and install the nexus-console package. Installation is done as root, since files created by root are readable and executable by everyone by default. Editable mode (`-e`) is optional; we use it to simplify maintenance and updates.

```bash
sudo python3.13 -m venv /opt/nexus/venv
sudo cp -r code/nexus-console /opt/nexus/
sudo /opt/nexus/venv/bin/pip install --no-cache-dir -e /opt/nexus/nexus-console
```

## 3. Device configuration

The device configuration is stored in `/etc`, which is reserved for configuration files, and can be installed as follows:

```bash
sudo install -D -m 644 device_config.yaml /etc/nexus/device_config.yaml
```

The `-D` flag creates any missing parent directories in the destination, and permissions are set using `-m 644` (owner: rw-, group: r--, others: r--).

## 4. Start the service

To activate the service, we need to copy the unit file, reload systemd and enable the service. Make sure to confirm the paths in `nexus.service` before enabling it.

```bash
sudo cp src/nexus_service/deployment/nexus.service /etc/systemd/system/nexus.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexus
```

On start, systemd creates `/run/nexus` (configured via `RuntimeDirectory=`) with owner `nexus` and mode `755` (owner: rwx, group: r-x, others: r-x). The service publishes `nexus.sock` and `authkey` in `/run/nexus`, where clients find them automatically. On stop, and after a crash, systemd removes `/run/nexus` again, so no stale socket or key survives. `/run` itself is owned by root, so only root can delete `/run/nexus`, and no other account can place files next to it.

Likewise, systemd creates `/var/log/nexus` (configured via `LogsDirectory=`) with owner `nexus` and mode `755`, and the service writes one log file per day (`<date>_nexus.log`) into it, as passed with `--log_dir`. Unlike `/run/nexus`, this directory is kept on stop. Without `--log_dir`, the log file is written to `~/nexus-console` of the account running the service, which the system account created above does not have, so the unit always passes `--log_dir`.

## 5. Usage and inspection

Any account connects without arguments; the examples from the user guide are unchanged:

```python
with AcquisitionControlManager() as manager:
    ...
```

### Acquisition data

The service does not store acquisition data. `manager.acquisition.run()` returns the
`AcquisitionData` object to the client, and `save()` / `save_ismrmrd()` run in the client
process, i.e. under the account which called them. Without a `user_path`, the data is written
to `~/nexus-console/<date>-session` of that account; with `user_path`, to the given directory.
No shared data directory has to be set up, and the service account needs no write access to
user directories.

The service is maintained and inspected with `systemctl` and `journalctl`. Changing the
state of the unit requires root, inspecting it does not:

| Task                                   | Command                                    |
| -------------------------------------- | ------------------------------------------ |
| Start at boot (and now)                | `sudo systemctl enable --now nexus`        |
| Do not start at boot (and stop now)    | `sudo systemctl disable --now nexus`       |
| Start / stop / restart                 | `sudo systemctl start\|stop\|restart nexus` |
| Reload unit file after editing it      | `sudo systemctl daemon-reload`             |
| Status, PID and last log lines         | `systemctl status nexus`                   |
| Is it running / enabled?               | `systemctl is-active nexus`, `systemctl is-enabled nexus` |
| Effective settings of the unit         | `systemctl show nexus -p User,ExecStart,RuntimeDirectory,StateDirectory` |
| Full log (terminal output)             | `journalctl -u nexus`                      |
| Log files                              | `ls -l /var/log/nexus`                     |
| Follow the log live                    | `journalctl -u nexus -f`                   |
| Log since last boot                    | `journalctl -u nexus -b`                   |
| Check socket and key are published     | `ls -l /run/nexus`                         |
