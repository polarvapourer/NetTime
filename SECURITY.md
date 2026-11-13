# Privacy and local data

The public source uses synthetic device names and test data. It includes no household Wi-Fi credentials, router password, access key, certificate pin, saved device selection, usage history or home-network address. Screenshots show example settings.

## Data created when you install NetTime

- The planner keeps its schedule and current-day bonus in your browser's localStorage. A schedule export includes the device label, daily allowances, exceptions and pause flag. It does not include router credentials or the current-day bonus. Review labels and schedules before sharing exports.
- The controller stores `config.json` and `state.json` in `~/.local/share/nettime` by default. The directory uses mode 700 and files use mode 600.
- Router authentication is stored locally so the service can run unattended. Its saved value is equivalent to the router password; it is not encrypted at rest. Never commit or upload the data directory.
- The dashboard access key is displayed when created and stored as a hash by the controller. Keep the displayed key private. It is not a router password.
- Device names and addresses are read locally from the router. They are not sent to the planner or to a cloud service.

## Deployment boundaries

The Pi dashboard binds to `127.0.0.1` and requires its access key for API requests. Reach it through SSH. Do not port-forward port 8787 or expose it through a public tunnel. The static planner can be hosted separately because it has no connection to your controller.

The router certificate is pinned before credentials are transmitted. The initial pin is a trust decision: verify you are talking to the intended router, and verify the fingerprint by a trusted route where possible. A later certificate change stops communication until setup is run again.

MAC filtering is not tamper-proof. The router API has no atomic list edit, so a concurrent change by another administrator can race with NetTime. Unknown state pauses automation but cannot guarantee that a device has internet access. Check the router directly if a rule is uncertain.

## Sharing or reporting a problem

Describe the steps, expected result, software version and a sanitised error. Do not include your data directory, HTTP authorisation headers, access-key URL fragment, router settings export or an unredacted device list. Public issues are visible to everyone. Do not post exploit details that expose a live installation.
