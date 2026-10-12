# 3 · Wake-on-LAN

> 🇫🇷 [Version française](../fr/03-wake-on-lan.md) · [← Back to the README](../../README.md)

Wake-on-LAN (WoL) turns the tower on by sending it a **magic packet** — 6 bytes of `FF` followed by its MAC address
16 times — which its network card listens for even when the PC is off.

> **The hard truth:** the packet is a LAN *broadcast*. It cannot cross the Internet. From outside your home
> (mobile data, school, a friend's Wi-Fi) something **inside the LAN** has to send it for you. That is what the
> "relay" and the "Freebox" options below are for.

## 1. Make the tower wakeable

1. **BIOS/UEFI** (essential — Windows cannot fix this): enable **Wake on LAN** / **Power On By PCI-E**
   (name varies: *Wake on PCIE/PCI*, *Resume by LAN*…) and **disable** *ErP Ready*, *EuP*, *Deep Sleep* — with those
   on, the network card is unpowered when the PC is off (the RJ45 port LEDs go dark).
2. **Windows**: `Setup-Tower.ps1` enables magic-packet wake on the Ethernet adapter, switches off Green Ethernet / EEE,
   and disables Fast Startup. Manual check: Device Manager → your Ethernet adapter → *Power Management* →
   "Allow this device to wake the computer" + "Only allow a magic packet…".
3. **Wired only.** Wi-Fi cards rarely support WoL from a full shutdown. Use Ethernet.
4. **Reserve the tower's LAN IP** in your router (static DHCP lease). It keeps `lan_ip` and your broadcast address stable.

Find the MAC address: `ipconfig /all` on the tower → "Physical Address" of the Ethernet adapter (`AA-BB-CC-DD-EE-FF`).
Put it in `connection.mac`.

## 2. Same network: the **Wake** button just works

RemoteHub sends the magic packet on **every network interface of the laptop** (Wi-Fi, Ethernet, virtual adapters) to each
address in `wake_on_lan.broadcasts` and on ports 9 and 7. Set the broadcast to your LAN:

```yaml
wake_on_lan:
  broadcasts: ["192.168.1.255", "255.255.255.255"]
```

(A network `192.168.1.0/24` has broadcast `192.168.1.255`.) After the packet, the badge turns yellow
("Booting…") for `health.boot_grace_s` seconds and green when SSH answers.

## 3. From outside the LAN

### Option A — a relay (works with any router)

An always-on LAN device reachable over Tailscale (Raspberry Pi, NAS, mini PC) sends the packet for you.

On the relay (Linux): install Tailscale, then `sudo apt install wakeonlan`. In `config.yaml`:

```yaml
wake_on_lan:
  relay:
    enabled: true
    host: "100.x.y.z"          # the relay's Tailscale IP
    user: "pi"
    key_file: "~/.ssh/id_ed25519"
    command: "wakeonlan {{mac}}"
```

Run `ssh pi@100.x.y.z` once so the relay's host key lands in `~/.ssh/known_hosts` (RemoteHub refuses unknown relays).

### Option B — the router's own WoL (Freebox, France)

The Freebox can send the packet from inside the LAN through its API, even when you are on mobile data.

1. Freebox OS → *Paramètres de la Freebox → Mode avancé → Accès distant* : enable **HTTPS remote access**.
2. At home: `python tools\register_freebox.py` and press the **✔ / right arrow** on the Freebox Server screen.
3. Freebox OS → *Gestion des accès → Applications* → RemoteHub-AI: tick **"Modification des réglages de la Freebox"**.
4. Set `freebox.enabled: true`.

The token is stored in `freebox_token.json` (git-ignored, treat it like a password).
Other routers: many (OpenWrt, pfSense, UniFi, Mikrotik…) can send WoL — use Option A or send a PR with a new provider!

## 4. Troubleshooting WoL

- **Test from the tower's LAN first**, with another PC: if that fails, the problem is BIOS/Windows, not RemoteHub.
- **Does it work after a shutdown but not after a power cut / long time off?** The card lost standby power: check the
  BIOS, the PSU switch, and ErP.
- **Wi-Fi repeaters / powerline adapters** sometimes rewrite MAC addresses (MAC-NAT). A *broadcast* still crosses them
  (the target MAC is in the packet's payload) but a *unicast* to the tower's IP does not. That is why broadcast is the default.
- **ARP:** routers forget the IP↔MAC mapping minutes after the tower is off, so unicast (`wake_on_lan.unicast`) is unreliable.
- Windows Fast Startup counts as a hibernation: `Setup-Tower.ps1` turns it off.

---

**Previous:** [← 2 · Laptop](02-laptop-setup.md) · **Next:** [4 · Linux VM →](04-linux-vm.md)
