# Changelog

## 1.3.0

- Update planner dependencies and pin CI actions to reviewed commits.
- Validate private controller data and record router write intent before changing the deny list.
- Bound dashboard connections and schedule imports, and support an independently verified router fingerprint during setup.
- Verify controller archives before replacing downloads and generate their SHA-256 checksum during packaging.

## 1.2.0

- Add opt-in weekday school hours: allow access without charging the allowance, including when leisure access is paused or exhausted.
- Add recurring away periods with per-period days, times and enable switches, including overnight periods. Away periods pause counting while keeping the normal access policy.
- Exclude scheduled periods at exact London time boundaries, preserve used time, and clear the previous metering sample when schedules are edited.
- Add controller and planner controls, status/preview explanations, validation, import/export support and migration from existing settings with both features disabled.

## 1.1.0

- Build, package and manage NetTime from Windows, Linux, Apple Silicon macOS or Intel macOS.
- Run the Python controller on the same computer or a separate always-on device; Raspberry Pi is optional.
- Add platform-specific private data directories, Windows ACLs, native interface discovery and a per-data-directory process lock.
- Replace Unix-only timezone setup with host-independent UK scheduling and DST boundaries.
- Add native startup management: Linux systemd, macOS LaunchAgent and Windows Task Scheduler. Windows/macOS jobs run at sign-in and require that user to remain signed in; all hosts must remain awake and connected.
- Publish a source-only `nettime-controller-1.1.0.zip`, preserving old packaging commands and the stable Pi download URL as aliases.
- Add a validated JSON command-driver interface and router compatibility/implementation guide. This is an extension point, not bundled support for every router brand. The built-in adapter remains Linksys JNAP.
- Expand CI to Windows, Linux, Apple Silicon macOS and Intel macOS for the controller and planner.

Before upgrading, turn blocking off, confirm access returns and stop the old controller. Keep private data outside the repository. Legacy data paths and Linksys configurations remain readable. Run only one controller per router/target.

## 1.0.0

First public release: the standalone schedule planner and Raspberry Pi controller, with setup documentation, certificate pinning and verified per-device router changes. The original release name was 0.2.0; 1.1.0 was originally named 0.3.0. Public releases now follow 1.x.0.
