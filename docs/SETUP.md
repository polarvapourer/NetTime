# Set up NetTime

Choose one path:

- **Explore the planner:** follow the [README quick start](../README.md#try-the-planner). This needs only a computer with Node.js and npm. Nothing is blocked.
- **Control a device at home:** use the steps below on your own network, with a Raspberry Pi that remains powered and connected.

All usernames, hosts and addresses below are placeholders or generic examples. Use your own values. Do not put passwords into commands, configuration files in this repository or GitHub issues.

## 1. Check requirements

- Raspberry Pi with a currently supported Raspberry Pi OS, Python 3 and systemd. The Python code retains 3.7 compatibility; a new installation should use a supported OS and Python release.
- Pi connected to the same home network as the router, over Wi-Fi or Ethernet. It does not need to carry the controlled device's traffic.
- Administrator access to a compatible Linksys JNAP router with MAC Filtering available in **Deny** mode. M60CF-EU is the tested model; firmware can differ. This is not a generic router integration.
- A stable per-network Wi-Fi address for the controlled device. Changing or rotating that address can bypass a MAC-based rule.
- An SSH client on the owner's computer. Windows PowerShell supports the commands below when OpenSSH Client is installed.

Do not change a router from Allow-list mode to Deny mode just to try NetTime. Review the router's existing configuration first. NetTime refuses incompatible mode rather than changing it.

## 2. Prepare a Pi without a keyboard

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on Windows, macOS or Linux. Select your Pi and Raspberry Pi OS Lite. In OS customisation, choose a hostname such as `nettime`, create your own user, configure your Wi-Fi details and enable SSH. Write a spare microSD card if you need to preserve an existing installation. Insert the card, power the Pi and allow first boot to finish.

See the official [headless setup guide](https://www.raspberrypi.com/documentation/computers/getting-started.html#headless-remote-setup). Older Pi models may require a 2.4 GHz Wi-Fi network. Keep OS and SSH credentials private.

In **Windows PowerShell**, set your own values and connect:

```powershell
$PiUser = "YOUR_PI_USER"
$PiHost = "nettime.local"
ssh "${PiUser}@${PiHost}"
```

Use the actual Pi hostname or its address from your router's device list if hostname discovery fails. Check the SSH host-key fingerprint when establishing trust for the first time.

## 3. Install the source on the Pi

The following commands run **inside the Pi SSH session**:

```bash
python3 --version
git --version
```

If Git, Python or timezone data is missing on Raspberry Pi OS:

```bash
sudo apt-get update
sudo apt-get install git python3 tzdata
```

Clone the public source and enter the controller directory:

```bash
git clone https://github.com/polarvapourer/NetTime-Portfolio.git
cd NetTime-Portfolio/controller
```

No `npm install` or `pip install` is needed on the Pi. The controller is independent of the React planner.

## 4. Configure the router connection

Find the router's LAN address in its administration interface. Replace `YOUR_ROUTER_ADDRESS` below:

```bash
python3 -m nettime setup --router YOUR_ROUTER_ADDRESS
```

Setup fetches the router certificate, displays its SHA-256 fingerprint and asks before saving the pin. Verify the intended router and fingerprint through a trusted route where possible. Then type the router administrator password at the hidden prompt. Setup performs a read-only API test; it does not activate blocking.

Save the NetTime access key somewhere private when it is displayed. It is shown once. Do not include it in screenshots or share the URL fragment containing it.

Run the diagnostic:

```bash
python3 -m nettime doctor
```

Check that router login, MAC-filter mode and device-list reads succeed. An API or permission failure is a compatibility issue to investigate before enabling enforcement. Never bypass certificate checks to make a test pass.

## 5. Start the persistent service

From the same controller directory, as your normal Pi user:

```bash
sh ./install-service.sh
systemctl status nettime --no-pager
```

The installer uses `sudo` for the systemd unit. It does not enable blocking on a new installation. The service starts at boot and restarts on failure. It runs independently of your laptop and SSH connection, while the Pi remains powered and on the network.

## 6. Open the real controller dashboard

In a **new Windows PowerShell window**, set your Pi values again and open a tunnel:

```powershell
$PiUser = "YOUR_PI_USER"
$PiHost = "nettime.local"
ssh -N -L 8787:127.0.0.1:8787 "${PiUser}@${PiHost}"
```

Leave that window open. After authentication it normally prints nothing. Open [http://127.0.0.1:8787](http://127.0.0.1:8787) in the browser and enter the saved NetTime access key.

The SSH password, router password and NetTime access key have separate purposes. The key is used only for this dashboard. Closing the tunnel hides the dashboard from your computer; it does not stop the controller.

## 7. Configure and test one device

1. Keep blocking **off** while checking the device list.
2. Confirm the intended device's per-network Wi-Fi address in its own settings. Use a stable address for this network. Do not select the Pi, router or an infrastructure node.
3. Set all seven daily allowances. Blank days mean setup is incomplete; zero means no leisure allowance for that day.
4. Edit or remove the sample **Study time** exception. It is an example, not your saved schedule. An exception permits all internet traffic, even after the allowance is exhausted, and does not charge minutes.
5. For the first test, use a device you control. Give it a short allowance, switch blocking on and confirm an actual website stops loading after exhaustion. Disable mobile data and other networks on the test device so they do not hide the result.
6. Switch blocking off and confirm internet access returns. A successful rule read-back alone does not establish that traffic was blocked.
7. Replace test allowances with your intended schedule before relying on the controller.

The Pi dashboard is authoritative. The React planner is independent; use its Export and the controller's Import to copy settings. Do not expect browser settings to sync automatically.

## 8. Maintenance and recovery

### Reopen the dashboard

Run the SSH tunnel command from step 6 again. If the browser says connection refused, confirm the tunnel window is still open. On the Pi, use `systemctl status nettime --no-pager` and `python3 -m nettime doctor` from the controller directory.

### Replace a lost dashboard key

On the Pi, from the controller directory:

```bash
python3 -m nettime new-key
sudo systemctl restart nettime
```

Save the replacement privately. Existing browser sessions need the new key.

### Update a source installation

Keep a trusted private backup of the data directory outside any repository. From the cloned repository root on the Pi:

```bash
sudo systemctl stop nettime
git pull --ff-only
sudo systemctl start nettime
systemctl status nettime --no-pager
cd controller
python3 -m nettime doctor
```

Review release changes before updating. Settings, usage and credentials live outside the repository. Saved enforcement resumes only after the controller revalidates router state; it may pause for review instead.

### Router certificate changed

Verify the change is expected, then rerun setup against your router. A certificate change is not a reason to disable TLS verification.

### Stop enforcing or uninstall

Turn blocking off in the Pi dashboard first and verify access has returned. Resolve any uncertain or pending block using the dashboard's review controls. Then:

```bash
sudo systemctl disable --now nettime
```

Stopping the service alone does not remove a router deny entry. If the Pi is unavailable, use the router's administration page to remove only the intended device's rule. Check the actual device afterwards. A manually changed rule causes NetTime to pause until reviewed.

## Alternative: install a portable ZIP

Download `public/downloads/nettime-pi-0.2.0.zip` using GitHub's **Download raw file** button, or build it from source with `python3 scripts/build_pi_zip.py`. Review [the packaged installation instructions](../controller/README.md). This route avoids cloning the whole project on the Pi.
