# Changelog

## 0.3.0

- Build, package and manage NetTime from Windows, Linux, Apple Silicon macOS or Intel macOS.
- Run the Python controller on the same computer or a separate always-on device; Raspberry Pi is optional.
- Add platform-specific private data directories, Windows ACLs, native interface discovery and a per-data-directory process lock.
- Replace Unix-only timezone setup with host-independent UK scheduling and DST boundaries.
- Add native startup management: Linux systemd, macOS LaunchAgent and Windows Task Scheduler. Windows/macOS jobs run at sign-in and require that user to remain signed in; all hosts must remain awake and connected.
- Publish a source-only `nettime-controller-0.3.0.zip`, preserving old packaging commands and the stable Pi download URL as aliases.
- Add a validated JSON command-driver interface and router compatibility/implementation guide. This is an extension point, not bundled support for every router brand. The built-in adapter remains Linksys JNAP.
- Expand CI to Windows, Linux, Apple Silicon macOS and Intel macOS for the controller and planner.

Before upgrading, turn blocking off, confirm access returns and stop the old controller. Keep private data outside the repository. Legacy data paths and Linksys configurations remain readable. Run only one controller per router/target.
