# NetTime local controller

Python standard-library service for per-device internet allowances on a compatible Linksys JNAP router. Public distribution 0.2.0. The dashboard binds to `127.0.0.1:8787`; access it through SSH.

The complete headless Wi-Fi, source-install and troubleshooting guide is at:
https://github.com/polarvapourer/NetTime-Portfolio/blob/main/docs/SETUP.md

## Install this portable package

Use a supported Raspberry Pi OS, Python 3, systemd and a Pi connected to your home network. Code compatibility starts at Python 3.7, but an old unsupported OS is not recommended for a new deployment. Router compatibility has been checked on an M60CF-EU; other models and firmware need separate validation.

Replace `YOUR_PI_USER`, `nettime.local` and `YOUR_ROUTER_ADDRESS` with your own values. The examples contain no saved household addresses.

In **Windows PowerShell**, after downloading `nettime-pi-0.2.0.zip`:

```powershell
$PiUser = "YOUR_PI_USER"
$PiHost = "nettime.local"
scp "$env:USERPROFILE\Downloads\nettime-pi-0.2.0.zip" "${PiUser}@${PiHost}:~/"
ssh "${PiUser}@${PiHost}"
```

In the **Pi SSH session**:

```bash
python3 -m zipfile -e ~/nettime-pi-0.2.0.zip ~/nettime
cd ~/nettime
python3 -m nettime setup --router YOUR_ROUTER_ADDRESS
python3 -m nettime doctor
sh ./install-service.sh
```

Setup displays the router certificate fingerprint, asks before pinning it, prompts for the router password without echoing it and performs a read-only test. Verify the intended router and fingerprint before trusting it. Save the displayed dashboard access key privately.

In a **new Windows PowerShell window**:

```powershell
$PiUser = "YOUR_PI_USER"
$PiHost = "nettime.local"
ssh -N -L 8787:127.0.0.1:8787 "${PiUser}@${PiHost}"
```

Leave the window open and visit http://127.0.0.1:8787. Enter your access key. No public port or firewall rule is needed.

## Configure and validate

Fresh setup keeps blocking off. Select a device after checking its stable per-network Wi-Fi address, set every day's allowance and edit the example Study time exception. Exceptions allow all internet traffic and consume no allowance. The timezone is Europe/London.

Test on a device you control: apply a short allowance, confirm actual internet traffic is blocked at exhaustion, then switch blocking off and confirm it returns. Router read-back is not proof that traffic stopped. Set realistic allowances after testing.

The service counts router-reported connected-and-allowed time, including idle periods. It is not screen-time measurement or app-specific blocking. Router outages, controller downtime and uncertain observations are not back-filled. Closing the laptop does not stop the service; the Pi must remain powered and connected.

## Data and safety

- Data is in `~/.local/share/nettime`, outside the application directory. Directory mode is 700; files use 600. Router authentication is password-equivalent and stored locally without encryption at rest. Never upload that folder.
- API requests require the dashboard access key. Other hosts/origins are refused. Do not expose port 8787 publicly.
- Router communication uses a pinned TLS certificate. A changed certificate stops communication until setup is repeated after verification.
- Only Deny mode is supported. NetTime preserves other entries, refuses infrastructure targets and never changes filter mode.
- Another administrator's edit or an unclear write pauses automation. Writes are read back, not repeated blindly. The API has no atomic list edit, so concurrent changes can still race.
- Turning blocking off stops automation and attempts to remove only the block it owns. An uncertain block needs review through the dashboard. Unselect is allowed only when no owned or pending block remains.
- The original controller was manually tested for block and restore on one compatible router and client. The public distribution's automated tests use synthetic data; validate your own installation before relying on it.

## Commands

Run these from this package directory:

```bash
python3 -m nettime doctor
python3 -m nettime new-key
sudo systemctl restart nettime
python3 -m unittest discover -s tests
```

`new-key` replaces the dashboard key; save it privately and restart the service afterwards. `doctor` is read-only. For foreground operation, use `python3 -m nettime serve` instead of installing the service.

Before stopping or removing NetTime, turn blocking off and confirm access returns. Stopping the service does not itself remove a router entry. If the Pi is unreachable, remove only the intended device's entry using the router administration page.

## Update a portable installation

Verify the new package and release notes, then stop the service, extract the new package over this directory and restart. Data remains in the separate private data directory. Run `doctor` afterwards. Do not rerun setup unless the router connection or certificate needs changing.
