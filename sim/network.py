# Renode Monitor extension: TAP on Windows/Linux, VMNET on macOS.
from System.Runtime.InteropServices import OSPlatform, RuntimeInformation
from threading import Timer


def mc_setup_network(tap_name, vmnet_socket):
    def run(command, hint=""):
        if monitor.Parse(command) == False:
            raise RuntimeError("Network setup failed: " + command + (". " + hint if hint else ""))

    if RuntimeInformation.IsOSPlatform(OSPlatform.OSX):
        # This is a Unix socket path, not a Renode @file to be downloaded.
        if any(c in vmnet_socket for c in ('"', '\\', '\n', '\r')):
            raise ValueError("vmnetSocket must be a Unix path without quotes or backslashes")
        run('emulation CreateVmnetHelper "{0}" "network"'.format(vmnet_socket))
    elif (RuntimeInformation.IsOSPlatform(OSPlatform.Linux) or
          RuntimeInformation.IsOSPlatform(OSPlatform.Windows)):
        if not tap_name or not all(c.isalnum() or c in '-_' for c in tap_name):
            raise ValueError("tapName must contain only letters, digits, hyphens or underscores")
        hint = "Create/configure the TAP adapter first; see sim/README.md."
        if RuntimeInformation.IsOSPlatform(OSPlatform.Windows):
            hint = ('In elevated PowerShell, install TAP-Windows6 and run '
                    'tapctl.exe create --hwid root\\tap0901 --name {0}; '
                    'verify it with tapctl.exe list and Get-NetAdapter. '
                    'Then run Renode as Administrator. See sim/README.md.').format(tap_name)
        run('emulation CreateTap "{0}" "network"'.format(tap_name), hint)
    else:
        raise RuntimeError("Host networking is supported on Windows, macOS and Linux")

    run('emulation CreateSwitch "network-switch"')
    run('connector Connect sysbus.ethernet network-switch')
    run('connector Connect host.network network-switch')


def mc_launch_sim(network, tap_name, vmnet_socket):
    if network:
        mc_setup_network(tap_name, vmnet_socket)
    # Schedule startup only after successful setup. Give UART time to attach
    # before the application's one-time boot output.
    startup = Timer(1.0, emulationManager.Instance.CurrentEmulation.StartAll)
    startup.start()
    try:
        if monitor.Parse('uart_connect sysbus.usart3') == False:
            raise RuntimeError("Unable to attach the USART3 console")
    finally:
        startup.cancel()
