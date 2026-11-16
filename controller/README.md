# NetTime controller 1.2.0

Run this Python controller on a separate always-on computer or on your main computer: Windows, macOS on Apple Silicon (M1 and newer) or Intel, and Linux including Raspberry Pi OS. Your management/build computer can use any of those platforms independently. No Pi or Node.js is required to run the controller.

The full guide covers both roles, transfers in either direction, background startup, router adapters and recovery:
https://github.com/polarvapourer/NetTime/blob/main/docs/SETUP.md

## Start from this package directory

On Windows PowerShell:

```powershell
py -3 -m nettime setup --router YOUR_ROUTER_ADDRESS
py -3 -m nettime doctor
py -3 -m nettime serve
```

On macOS (Apple Silicon or Intel), Linux or Raspberry Pi:

```bash
python3 -m nettime setup --router YOUR_ROUTER_ADDRESS
python3 -m nettime doctor
python3 -m nettime serve
```

The built-in adapter targets compatible Linksys JNAP routers. Only M60CF-EU has a recorded live block/restore check. Other brands need an adapter implementing their actual management interface; there is no universal blocking API. Read `ROUTERS.md` in this package before using another router.

Setup pins the router certificate after your confirmation and reads its settings without enabling blocking. Keep the displayed dashboard key private. The password prompt is hidden. Stop foreground operation with Ctrl+C before optionally running `service install` using the same Python command.

| Host | Background startup |
| --- | --- |
| Linux with systemd | `python3 -m nettime service install`: boot service as your normal user; sudo needed to install |
| macOS | `python3 -m nettime service install`: LaunchAgent at login, while the user remains logged in |
| Windows | `py -3 -m nettime service install`: Task Scheduler at sign-in, while the user remains signed in |

Use `service status`, `start`, `stop`, `restart`, or `remove` to manage it. Windows/macOS user jobs do not run after logout. Foreground operation works without these optional installers. Keep the host awake and connected; a terminal on a sleeping or powered-off device cannot enforce a schedule.

## Dashboard and validation

On the controller itself, open http://127.0.0.1:8787. From a different Windows/Mac/Linux computer with SSH access configured, run:

```text
ssh -N -L 8787:127.0.0.1:8787 YOUR_USER@YOUR_CONTROLLER
```

Leave the tunnel running, then open the same address on that computer. Enter the dashboard access key. No public port is needed. Closing your management computer does not stop a separate controller.

Keep blocking off while selecting a device and setting all seven allowances. Verify its stable per-network address, edit the sample Study time exception, then test actual blocking and restoration on your own device. The controller never changes an incompatible filter mode. It preserves unrelated rules, refuses known infrastructure targets and pauses on uncertain changes. Unselect is available when no owned or pending block remains.

Allowances measure connected-and-allowed time, including idle periods, not screen time. The timezone is Europe/London, independent of the host timezone, using UK DST rules since 1996. Downtime is not back-filled. A rule can remain blocked when the controller is off; resolve that through the router if needed.

## Private data

Windows: `%LOCALAPPDATA%\NetTime`; macOS: `~/Library/Application Support/NetTime`; Linux: `~/.local/share/nettime`. A legacy directory containing config is retained. Override with `NETTIME_DATA` or `--data-dir` before the subcommand; use one directory consistently. Run only one controller per router/target. A process lock protects the same local data directory.

POSIX uses 700/600 modes; Windows uses current-user/SYSTEM ACLs. Credentials are password-equivalent and unencrypted at rest. Never upload the data directory. Read the repository's SECURITY.md for boundaries.

Before updating or moving devices, turn blocking off and confirm internet returns, then stop the old job. Replace this package and restart it, keeping the separate private data folder. Reinstall the background job if its Python executable or package path changes. Run `doctor` afterwards. Stopping/removing the job does not remove router rules.

## School hours and away periods

In the controller dashboard's Schedule section, enable School hours and set its start/end times. This applies Monday–Friday, allows access even with no allowance left or while leisure access is paused, and never uses allowance minutes. Turn it off for school holidays. It starts disabled after an update.

Use Add away period to enter a name, days, departure/return times and an enabled switch. Up to ten recurring periods are supported. Away periods stop allowance counting only: normal access rules still apply. For a period crossing midnight, tick the day you leave (for example Sunday 22:00 to Monday 07:00). Equal start/end times are rejected.

Press Save schedule. All times use Europe/London, including BST/GMT changes. Starts are included; ends are excluded. Overlaps never charge twice. School hours and existing allowed exceptions take priority over exhausted or paused leisure access. Used time is retained when a period ends.

These are scheduled exclusions, not detection of screen locking or actual absence. Outside them an idle, connected and allowed device can still use its allowance. The Linksys MAC filter still denies Wi-Fi association while blocked.

Existing settings without these fields load with school hours disabled and no away periods. Settings exports now include schoolHours and awayWindows; older program versions cannot read these exports. Keep a private backup before updating or downgrading. Login, key, selected device, usage and other exceptions are retained.
