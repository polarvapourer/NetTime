# Set up NetTime on Windows, macOS or Linux

Two devices can have separate roles:

- **Management computer:** where you edit, build, package, copy files and open the dashboard. Windows, Linux and macOS on Apple Silicon (M1 and newer) or Intel are supported.
- **Controller device:** where the Python scheduler runs. This can be a separate always-on desktop, mini PC, laptop, server or Raspberry Pi. It can also be the management computer. It must remain awake, powered and connected to the controlled network.

The controller does not need to carry the target device's traffic. Wi-Fi or Ethernet is fine. A terminal alone is not enough: the host needs Python, writable private storage and network access to the router. Phones/tablets with restricted background execution are not supported controller hosts.

## Requirements

| Task | Install on the device doing that task |
| --- | --- |
| Edit/build the browser planner | Git, Node.js 22.12+ and npm |
| Build a portable controller ZIP | Python 3; Node/npm optional |
| Run the controller | Python 3, a compatible router adapter, local private storage |
| Manage a separate controller | An SSH client; the controller must have a separately configured SSH server |

Use supported OS and Python releases for new installations. Python 3.12 is the CI baseline; legacy controller syntax remains compatible with Python 3.7. The controller uses only Python's standard library. The planner has separate npm dependencies.

Install Python from [python.org](https://www.python.org/downloads/). Its macOS **universal2** installer supports Apple Silicon and Intel natively; Rosetta is not required. Use native ARM64 Node.js on Apple Silicon and x64 Node.js on Intel Macs from [nodejs.org](https://nodejs.org/en/download). On Linux, your distribution's maintained Python package is suitable. On Windows, verify `py -3 --version`; on macOS/Linux, verify `python3 --version`.

## 1. Get and build the program on your management computer

These Git and npm commands work in Windows PowerShell, macOS Terminal and a Linux shell:

```text
git clone https://github.com/polarvapourer/NetTime.git
cd NetTime
npm ci
npm test
npm run typecheck
npm run build
npm run dev
```

Open the local URL printed by Vite. If PowerShell blocks the npm script launcher, use `npm.cmd` in place of `npm`; no global execution-policy change is needed. Do not copy `node_modules` between operating systems or CPU architectures. Run `npm ci` on each machine instead. The production `dist/` contains static files that can be served on any of these platforms; application routes need an `index.html` fallback.

To build the controller package from the same repository root:

```text
npm run package:controller
```

Or use Python directly, with no Node installation:

```powershell
# Windows PowerShell
py -3 scripts/build_controller_zip.py
```

```bash
# macOS (Apple Silicon or Intel) / Linux
python3 scripts/build_controller_zip.py
```

All platforms produce the same source-only `public/downloads/nettime-controller-0.3.0.zip`. There is no separate M1, Intel, Windows or Pi binary. Download the release ZIP instead if you do not want to build it. `build_pi_zip.py`, `package:pi` and the stable `nettime-pi.zip` URL remain compatibility aliases.

## 2. Put the controller on the device that will stay on

If it is the same computer, enter `NetTime/controller` and skip the transfer. If it is a different computer, you can clone the repo there and enter `NetTime/controller`, or copy the controller ZIP using SCP, a network share or USB.

For a separate macOS/Linux/Pi controller with SSH already configured, this works from Windows PowerShell, macOS Terminal or Linux. Replace both placeholders:

```text
scp public/downloads/nettime-controller-0.3.0.zip YOUR_USER@YOUR_CONTROLLER:nettime-controller.zip
ssh YOUR_USER@YOUR_CONTROLLER
```

Once signed into that controller:

```bash
python3 -m zipfile -e ~/nettime-controller.zip ~/nettime
cd ~/nettime
```

For a Windows controller, copy the ZIP to its Downloads folder, open PowerShell **on that controller** and run:

```powershell
py -3 -m zipfile -e "$env:USERPROFILE\Downloads\nettime-controller-0.3.0.zip" "$env:USERPROFILE\nettime"
cd "$env:USERPROFILE\nettime"
```

The package is extracted directly into that folder; the Git source checkout instead uses its `controller` subfolder. Keep its final location stable after installing a background job.

For a headless Raspberry Pi, [Raspberry Pi Imager](https://www.raspberrypi.com/software/) can preconfigure Wi-Fi, your own user and SSH. See its [headless setup instructions](https://www.raspberrypi.com/documentation/computers/getting-started.html#headless-remote-setup). A Pi is optional. Windows and macOS SSH servers need their own OS setup; installing NetTime does not enable remote login or change a firewall.

## 3. Check your router and set up the controller

Read [Router compatibility and adapters](ROUTERS.md) first. Being on the same network does not make a router compatible. NetTime must be able to read connected devices and read/write per-device deny rules without replacing unrelated rules.

For the built-in Linksys JNAP adapter, run these commands **on the controller**, inside its package directory. Replace `YOUR_ROUTER_ADDRESS` with its LAN IPv4 address:

```powershell
# Windows
py -3 -m nettime setup --router YOUR_ROUTER_ADDRESS
py -3 -m nettime doctor
py -3 -m nettime serve
```

```bash
# macOS / Linux / Raspberry Pi
python3 -m nettime setup --router YOUR_ROUTER_ADDRESS
python3 -m nettime doctor
python3 -m nettime serve
```

Setup displays the certificate fingerprint for you to verify, prompts for the router password without echoing it and performs a read-only API test. It saves a dashboard access key; keep that private. A fresh installation leaves blocking off. Do not disable certificate checks to make a connection work.

Foreground `serve` works on all supported platforms and continues while that process is running. Closing its terminal stops it. Use Ctrl+C to stop before installing the background job.

## 4. Run in the background

From the controller package directory, use the same Python interpreter used for setup:

```powershell
# Windows
py -3 -m nettime service install
py -3 -m nettime service status
```

```bash
# macOS / Linux
python3 -m nettime service install
python3 -m nettime service status
```

| Controller OS | Startup mechanism | When it runs |
| --- | --- | --- |
| Linux with systemd, including Raspberry Pi OS | System service, running as your ordinary user; installation uses sudo | At boot, without an interactive login; restarts on failure |
| macOS, Apple Silicon or Intel | Current-user LaunchAgent | At user login and while that account remains logged in; restarts on failure |
| Windows | Current-user Task Scheduler job; no password stored | At user sign-in and while that account remains signed in; retries failures |
| Linux without systemd / another terminal environment | Foreground `serve` or your own process supervisor | While that process is running |

Windows/macOS user jobs survive closing Terminal/PowerShell and locking the screen, but **not logout**. They are not system boot services. For a controller that must run before any login, use the Linux systemd route or an appropriately administered OS service of your own. Keep sleep/hibernation disabled while relying on enforcement; NetTime does not change power settings. Closing a laptop lid may suspend it.

On Windows, an organisation's PowerShell/script policy may block the optional installer. Use foreground `serve` or ask the administrator to approve the reviewed script; NetTime does not bypass that policy. On macOS, the LaunchAgent needs an existing logged-in GUI user session. Foreground operation also works over SSH.

## 5. Open the dashboard

**On the controller itself:** open http://127.0.0.1:8787 in its browser. No SSH tunnel is needed.

**On a different computer:** with SSH access already configured on the controller, open a terminal on your management computer and run:

```text
ssh -N -L 8787:127.0.0.1:8787 YOUR_USER@YOUR_CONTROLLER
```

This command works from Windows, macOS and Linux. Check the host-key fingerprint on first connection. Leave the tunnel running; a successful tunnel usually prints nothing. Open http://127.0.0.1:8787 on the management computer and enter the dashboard key. The dashboard remains loopback-only; do not expose or port-forward 8787.

Your management computer can disconnect or shut down after saving settings; a separate controller keeps running. Shutting down, sleeping or disconnecting the controller stops scheduling. Existing router blocks may remain until the controller returns or you remove the intended rule manually.

## 6. Configure and test a device

1. Keep blocking off. Find the intended device and verify its stable per-network Wi-Fi/Ethernet MAC address in its own settings. Do not select the controller, router or Wi-Fi nodes.
2. Set every day's allowance. Blank means incomplete setup; zero means no leisure allowance.
3. Edit/remove the sample Study time exception. Exceptions permit all traffic and do not consume allowance. Scheduling uses Europe/London time, regardless of either computer's timezone.
4. Test with a device you own: use a short allowance, enable blocking, and confirm actual internet access stops at exhaustion. Disable other networks/mobile data on the test device during the test.
5. Turn blocking off and confirm access returns. A router's successful API response is not enough to establish enforcement.
6. Set your real allowances only after both directions work.

The controller dashboard is authoritative. The separate planner uses Export/Import to transfer schedules; they do not sync automatically. Time counted is router-reported connected-and-allowed time, including idle time, not screen time. Gaps during sleep, outages or stopped processes are not back-filled.

## Data, maintenance and moving to another controller

Default private data locations:

| OS | Location |
| --- | --- |
| Windows | `%LOCALAPPDATA%\NetTime` |
| macOS | `~/Library/Application Support/NetTime` |
| Linux / Raspberry Pi | `~/.local/share/nettime` |

Existing `~/.local/share/nettime/config.json` is detected first to preserve old installations. `NETTIME_DATA` or `--data-dir` explicitly selects another location. Put `--data-dir` before the subcommand and use the same location for setup, serve and service commands. Keep it on a local filesystem with working permissions/ACLs; do not use a shared or cloud-synced folder.

POSIX directories/files use 700/600; Windows uses a protected DACL for the current account and SYSTEM. Saved router authentication is password-equivalent and not encrypted at rest. Do not upload that folder.

Use `service status`, `service stop`, `service start`, `service restart` or `service remove` with your OS's Python command. `remove` disables startup (and leaves the inactive Linux unit file). Before stopping/removing or moving controllers, turn blocking off and verify access returns. Stopping does not remove a rule. Run only one controller for a target/router; a local lock prevents duplicate processes sharing one data directory, not separate machines.

To update, stop the background job, review the release changes, update source with `git pull --ff-only` or replace package files, then start it and run `doctor`. After interpreter/path changes, reinstall the background job so it points to the intended Python. Do not rerun setup for routine updates.

For a lost key: stop the job, run `new-key`, save the displayed replacement privately, then start it. For a certificate change, verify the reason before repeating setup. To move to another controller, first turn the old one off and disable its job, set up the new device from scratch, then import a schedule and retest. Never run both at once. Keep any private backups outside the repository.
