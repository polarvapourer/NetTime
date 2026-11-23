# Privacy and local data

The public source uses synthetic device names and test data. It includes no household Wi-Fi credentials, router password, access key, certificate pin, saved device selection, usage history or home-network address. Screenshots show example settings.

## Data created when you install NetTime

- The planner keeps its schedule and current-day bonus in your browser's localStorage. A schedule export includes the device label, daily allowances, exceptions and pause flag. It does not include router credentials or the current-day bonus. Review labels and schedules before sharing exports.
- The controller stores `config.json` and `state.json` outside the repository at `%LOCALAPPDATA%\NetTime` on Windows, `~/Library/Application Support/NetTime` on macOS, or `~/.local/share/nettime` on Linux. Existing legacy data is retained. POSIX uses directory/file modes 700/600. Windows uses a protected DACL for the current account and SYSTEM. Keep the data in a trusted local path whose parent directories cannot be modified by untrusted users.
- Router authentication is stored locally so the service can run unattended. Its saved value is equivalent to the router password; it is not encrypted at rest. Never commit or upload the data directory.
- The dashboard access key is displayed when created and stored as a hash by the controller. Keep the displayed key private. It is not a router password.
- Device names and addresses are read locally from the router. They are not sent to the planner or to a cloud service.

## Deployment boundaries

The controller dashboard binds to `127.0.0.1` and requires its access key for API requests. Open it locally or reach it through SSH from another computer. Do not port-forward port 8787 or expose it through a public tunnel. The static planner can be hosted separately because it has no connection to your controller.

The router certificate is pinned before credentials are transmitted. Use `setup --expected-fingerprint` with a SHA-256 fingerprint obtained through a trusted route. Interactive setup otherwise relies on your verification of the displayed fingerprint. A later certificate change stops communication until setup is run again.

MAC filtering can be bypassed by changing the device address. The router API has no atomic list edit, so a concurrent change by another administrator can race with NetTime. An interrupted write pauses automation. If a block is present after an unconfirmed add, verify its ownership in the router before confirming its removal.

## Sharing or reporting a problem

Describe the steps, expected result, software version and a sanitised error. Do not include your data directory, HTTP authorisation headers, access-key URL fragment, router settings export or an unredacted device list. Public issues are visible to everyone. Do not post exploit details that expose a live installation.

## External router drivers

Command drivers are trusted code running as the controller account. They receive password-equivalent configuration over stdin and must implement their own verified TLS/SSH connection and safe router edits. NetTime suppresses raw driver stderr, validates response schemas and reads back writes; these checks cannot establish that a dishonest driver or unsupported firmware enforced a rule. Never run an unreviewed driver or publish its configuration. Only one controller should manage a given router/target at a time.
