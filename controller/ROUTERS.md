# Router compatibility and adding another brand

NetTime's controller can run on Windows, macOS or Linux independently of your router brand. **Router enforcement is a separate compatibility requirement.** There is no universal router command for blocking a device's internet access. A router must expose suitable management controls, and an adapter must implement its actual API/SSH interface. Installing NetTime alone does not add those controls to a router.

## What is supported now?

| Router/interface | Status |
| --- | --- |
| Linksys/Community Fibre M60CF-EU with the expected local JNAP MAC-filter API | Built-in adapter; original block/restore path checked on one router and client |
| Other Linksys models/firmware with the same API | Possible compatibility; run read checks and actual block/restore validation |
| TP-Link, ASUS, NETGEAR, AVM/FRITZ!Box, Ubiquiti, MikroTik, OpenWrt and other brands/firmware | No bundled live-tested adapter; use a separately implemented and validated command adapter |
| Router with no suitable local API/SSH controls | Cannot enforce through the router with this release |

The command adapter makes the engine independent of the brand, but it is an extension interface, **not a list of newly supported routers**. Neither UPnP discovery nor knowing a router password guarantees an internet-blocking API. DNS-only blocking is not equivalent to blocking internet access. A manufacturer's parental-control feature may require its cloud service, have different semantics or not be available to external programs.

## 1. Find the exact model and interface

1. Open your router's administration page. Record the manufacturer, model and firmware version privately. ISP-customised firmware may differ from the retail model.
2. Consult that model's official documentation for supported local API, SSH/CLI or an integration it explicitly supports. Prefer a local interface with certificate or SSH host-key verification. Check authentication and account permissions.
3. Confirm the interface can list client MAC addresses **and current connection state**, identify router/mesh nodes, read all per-device deny rules, and change the intended rule without resetting unrelated settings. An interface that only lists DHCP leases cannot reliably measure connected time.
4. Check what the rule actually blocks. Some “MAC filters” deny Wi-Fi association rather than just internet access. IPv6, Ethernet, mesh nodes and private addresses need testing.
5. Do not enable remote internet administration or replace firmware just to follow this guide. If there is no suitable documented interface, this release cannot automate that router; use the manufacturer's controls, use the standalone planner, or use supported network equipment.

Do not try the Linksys adapter against another brand and expect it to detect its protocol. There are no default credentials or guessed vendor endpoints in NetTime.

## 2. Use an existing trusted driver, or implement one

A developer familiar with the router's supported interface can implement `examples/router_driver.py`. It is intentionally a non-working starter and refuses every operation until implemented. Review any third-party driver before running it: it runs as your controller account and receives private router configuration. A successful driver response must describe actual router state, never simulated success.

A Python driver works unchanged across host CPUs if its dependencies do. For another executable, install the matching Windows/macOS/Linux and CPU build on the controller. Put the reviewed driver in a stable local path outside any downloaded temporary directory.

The controller runs the driver directly, without a shell. A `.py` file uses the same Python interpreter as NetTime. Each request starts a process with one UTF-8 JSON object on stdin:

```json
{"protocol": 1, "action": "get_filter", "config": {}, "arguments": {}}
```

`config` is the private object you supply at setup. Do not log it. Return exactly one JSON object on stdout, with exit code zero on success:

```json
{"ok": true, "output": {"mode": "Deny", "macs": [], "max": 64}}
```

On failure, return `{"ok": false}` and/or a nonzero exit status. Keep any diagnostics local and redact credentials. NetTime discards driver stderr and does not echo raw driver errors. Requests time out after 20 seconds and responses are size checked. Credentials travel on stdin, not in process arguments.

### Required operations

| Action | Arguments | Successful `output` |
| --- | --- | --- |
| `get_filter` | `{}` | `{"mode":"Deny","macs":["02:00:00:00:00:10"],"max":64}`; all existing entries, actual mode and capacity |
| `set_filter` | `{"mode":"Deny","macs":[...]}` | `{}` only after submitting the requested list; the engine separately reads back confirmation |
| `get_devices` | `{}` | Device array, as below; a failed observation must fail, not return a fabricated empty list |
| `get_local_device_id` | `{}` | Controller's router-side device ID string, or `null` if unavailable; local interface identity must then be available |

Example `get_devices` output (synthetic):

```json
[
  {
    "id": "example-client",
    "name": "Example tablet",
    "macs": ["02:00:00:00:00:10"],
    "connectedMacs": ["02:00:00:00:00:10"],
    "isAuthority": false,
    "nodeType": null
  }
]
```

`macs` contains known interfaces; `connectedMacs` contains only currently connected interfaces and must be a subset of `macs`. Include router/mesh nodes and mark them with `isAuthority: true` or `nodeType: "Master"`/`"Slave"`. Never mark infrastructure as an ordinary client to make validation pass. If neither host interfaces nor router-side controller identity is available, activation is refused.

The engine requires a Deny policy. Do not map an Allow policy to Deny just by changing the response text. If the native router API has no equivalent semantics, write a different engine integration and tests rather than using this contract incorrectly. `set_filter` must preserve unrelated firewall and parental-control configuration. The engine preserves other entries in the returned list, but cannot detect hidden configuration your driver erased. Implement authentication, TLS/SSH verification, session expiry and firmware-specific errors in the driver; the Linksys adapter's certificate pin does not automatically protect external drivers.

## 3. Prepare private driver configuration on the controller

The keys are defined by your actual driver, not by NetTime. Create a JSON object containing only the settings that driver needs, outside the repository, without putting passwords into shell command history. Protect the file before setup.

On macOS/Linux:

```bash
chmod 600 /ABSOLUTE/PRIVATE/PATH/router-driver.json
python3 -m nettime setup --adapter command --driver /ABSOLUTE/PATH/router_driver.py --driver-config /ABSOLUTE/PRIVATE/PATH/router-driver.json
python3 -m nettime doctor
```

On Windows PowerShell, from the controller directory, use NetTime's native ACL helper on your existing private JSON file:

```powershell
py -3 -c "from nettime.windows_acl import protect; protect(r'C:\PRIVATE\router-driver.json')"
py -3 -m nettime setup --adapter command --driver "C:\DRIVERS\router_driver.py" --driver-config "C:\PRIVATE\router-driver.json"
py -3 -m nettime doctor
```

Replace every path. Setup copies the private JSON object into NetTime's protected config. Keep or securely remove your original file according to your backup needs. Never commit either file. The driver path is retained, so keep that code in place. Setup performs read operations, not `set_filter`, and does not establish that enforcement works.

## 4. Validate before enabling normal operation

Use a spare/test device and save a private router backup. Keep an independent route to router administration. Start the dashboard with blocking off, verify the device list and refusal to select the controller/router, then:

1. Record existing unrelated deny rules.
2. Set a short allowance for your test device; switch blocking on.
3. Confirm actual external traffic is denied after exhaustion, including IPv4/IPv6 paths applicable to your network. Confirm unrelated clients and rules still work.
4. Switch blocking off; confirm actual access returns and unrelated rules remain intact.
5. Test a restart, an unavailable router, a rejected login and a manual rule change. Unknown state must pause/stop changes; the driver must not claim success.
6. Only then use ordinary allowances. Record the exact model/firmware and driver version as the scope of your validation.

The test suite checks the command protocol with synthetic drivers; it does not establish support for every brand. If your router needs a new adapter, its official model-specific API documentation and sanitised request/response examples are needed to implement and verify it. Do not share passwords, live headers, certificates with private keys or unredacted network exports in public issues.
