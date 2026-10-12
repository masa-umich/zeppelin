# STM32H725 host networking

The launcher currently enables host networking by default. To connect its
inherited Ethernet model to your computer, complete the OS setup below, then run:

```sh
renode --disable-gui --console -e '$network=true; $elf=@osprey-app/build/zephyr/zephyr.elf; include @sim/stm32h725.resc'
```

The single-quoted command works in POSIX shells and PowerShell. On Windows, run
it in PowerShell, not Command Prompt. Add `$quiet=false;` to see model warnings.
The launcher detects the OS, creates a switch, and connects `sysbus.ethernet`
and the host interface before starting emulation. It does not install drivers,
change host addresses, or bridge your physical LAN. Use a fresh Renode process
for each run; the named bridge/switch are created once.
Bridge setup errors stop startup; the launcher does not fall back to a
disconnected simulation. For serial-only use without network prerequisites:

```sh
renode --disable-gui --console -e '$network=false; $elf=@osprey-app/build/zephyr/zephyr.elf; include @sim/stm32h725.resc'
```

Defaults:

| Setting | Value |
| --- | --- |
| Linux/Windows TAP adapter (`$tapName`) | `renode-tap0` |
| macOS helper socket (`$vmnetSocket`) | `/tmp/renode-vmnet.sock` |
| Host address in the examples | `192.168.100.1/24` |
| Suggested firmware address | `192.168.100.2/24` |

Choose a different subnet on both sides if this conflicts with your LAN/VPN.
Override an adapter/socket with, for example, `$tapName="my-tap";` or
`$vmnetSocket="/tmp/my-vmnet.sock";` before including the launcher.

## Linux

Install `iproute2` (for example `sudo apt install iproute2` on Debian/Ubuntu).
Linux's TUN/TAP driver must be available as `/dev/net/tun`; if missing, try
`sudo modprobe tun`. Containers/WSL need their own device and permission setup;
these instructions target a normal Linux host.

Create a persistent TAP owned by your user, and configure it **before** launching:

```sh
sudo ip tuntap add dev renode-tap0 mode tap user "$(id -un)"
sudo ip addr add 192.168.100.1/24 dev renode-tap0
sudo ip link set dev renode-tap0 up
```

Run Renode as that user with the network command above. Skip creation if the
adapter already exists; inspect it with `ip addr show renode-tap0`. Persistence
here means across Renode runs, not across host reboots. To remove it after
closing Renode: `sudo ip tuntap del dev renode-tap0 mode tap`.

## Windows

Install [OpenVPN Community](https://openvpn.net/community-downloads/) with the
**TAP-Windows6** component. A Wintun-only installation is insufficient. You do
not need a VPN connection. Renode documents OpenVPN 2.5.6 as a tested version;
driver paths/components can differ in newer installers.

In an elevated PowerShell, create the adapter and assign its address:

```powershell
& "$env:ProgramFiles\OpenVPN\bin\tapctl.exe" create --hwid 'root\tap0901' --name renode-tap0
& "$env:ProgramFiles\OpenVPN\bin\tapctl.exe" list
Get-NetAdapter -Name renode-tap0 | Format-List Name, InterfaceDescription, Status, InterfaceGuid
netsh interface ipv4 set address name="renode-tap0" static 192.168.100.1 255.255.255.0
```

If `tapctl.exe` is elsewhere, use the installed path. Skip creation if the
adapter already exists. Run the Renode network command in an elevated
PowerShell. Check that the adapter is enabled in Windows network settings.
Allow your chosen test application's traffic on this adapter in Windows
Firewall if blocked; no default gateway is required for host-only traffic.
To remove the adapter, use `tapctl.exe list`, then `tapctl.exe delete <GUID>`.

### “Failed to retrieve the GUID of the TAP device”

Installing OpenVPN does not guarantee an adapter named `renode-tap0` exists.
First run the `tapctl.exe list` and `Get-NetAdapter` commands above. The named
adapter must use TAP-Windows6, not Wintun or OpenVPN DCO. The explicit hardware
ID in the creation command requests the TAP-Windows driver.

If it is missing, create it using the command above. If an existing TAP adapter
has another name, either rename it or set `$tapName="that-name";` in the Renode
command. The launcher accepts adapter names containing letters, digits, hyphens
and underscores. If creation fails, repair the OpenVPN installation with its
TAP-Windows6 component enabled, then retry from an elevated PowerShell. Adapter
status may be disconnected before Renode opens it; that alone is not a failure.

References: [Renode Windows TAP setup](https://renode.readthedocs.io/en/latest/networking/host-network.html#using-tap-interface-on-windows),
[OpenVPN tapctl](https://community.openvpn.net/Pages/Tapctl).

## macOS

Use VMNET rather than installing a TAP kernel extension. On macOS 26 or later:

```sh
brew install nirs/vmnet-helper/vmnet-helper
"$(brew --prefix vmnet-helper)/libexec/vmnet-helper" \
  --socket /tmp/renode-vmnet.sock \
  --operation-mode host \
  --start-address 192.168.100.1 \
  --end-address 192.168.100.10 \
  --subnet-mask 255.255.255.0
```

Keep this process running in a separate terminal, wait for its socket-ready
message, then launch Renode. macOS 26 runs this helper without `sudo`.
Use **vmnet-helper v0.12.0 or later**: earlier versions ignore address settings
in host mode. Check its reported network matches the firmware subnet.

On macOS 15 or earlier, install using the upstream
[installation instructions](https://github.com/nirs/vmnet-helper), then run
`sudo /opt/vmnet-helper/bin/vmnet-helper` with the same arguments. Ensure the
Unix socket is accessible to the user running Renode, following the upstream
[sudo guide](https://github.com/nirs/vmnet-helper/blob/main/docs/sudo.md).

Stop the helper after quitting Renode, and restart it for each new simulation;
the helper serves one connected client. `host` mode provides host connectivity.
For outbound Internet access, use `shared` mode and configure the firmware's
gateway/DNS; Linux/Windows TAP would additionally require host routing/NAT.

## Firmware and verification

The bridge does not enable networking inside an ELF. The current Osprey hello
build has `CONFIG_NETWORKING` disabled. Build firmware that enables Zephyr
networking, Ethernet, IPv4 and the needed sockets/TCP/UDP support, with its
STM32 Ethernet/MDIO/PHY drivers. Give the interface a unique MAC and a static
`192.168.100.2` address with netmask `255.255.255.0`; turn off DHCP for this
initial test. The Nucleo H723 board definition already enables Ethernet and
MDIO, but successful driver/PHY initialization against Renode must be verified.

Start with a TCP/UDP echo server. Connect to `192.168.100.2:<port>` from the host
and verify a reply. A ping also needs firmware ICMP support. In the firmware,
the host is `192.168.100.1`, not `127.0.0.1`. This setup does not automatically
publish the guest service on localhost; add a host port forwarder if desired.
Allow longer client timeouts because Renode uses virtual time.

Validated here: serial-only launch, helper import, and OS selection/command
generation. Live bridge traffic requires the host prerequisites and a
network-enabled ELF; Windows/Linux adapters and macOS VMNET traffic have not
been tested in this workspace.

References: [Renode host networking](https://renode.readthedocs.io/en/latest/networking/host-network.html),
[Renode switches](https://renode.readthedocs.io/en/latest/networking/wired.html),
[VMNET integration](https://github.com/nirs/vmnet-helper/blob/main/docs/integration.md),
[Linux TUN/TAP](https://www.kernel.org/doc/Documentation/networking/tuntap.txt).
