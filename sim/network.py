# Renode Monitor extension: TAP on Windows/Linux, VMNET on macOS.
from System.Runtime.InteropServices import OSPlatform, RuntimeInformation


def mc_setup_network(tap_name, vmnet_socket):
    def run(command):
        if monitor.Parse(command) == False:
            raise RuntimeError("Network setup failed: " + command)

    if RuntimeInformation.IsOSPlatform(OSPlatform.OSX):
        # This is a Unix socket path, not a Renode @file to be downloaded.
        if any(c in vmnet_socket for c in ('"', '\\', '\n', '\r')):
            raise ValueError("vmnetSocket must be a Unix path without quotes or backslashes")
        run('emulation CreateVmnetHelper "{0}" "network"'.format(vmnet_socket))
    elif (RuntimeInformation.IsOSPlatform(OSPlatform.Linux) or
          RuntimeInformation.IsOSPlatform(OSPlatform.Windows)):
        if not tap_name or not all(c.isalnum() or c in '-_' for c in tap_name):
            raise ValueError("tapName must contain only letters, digits, hyphens or underscores")
        run('emulation CreateTap "{0}" "network"'.format(tap_name))
    else:
        raise RuntimeError("Host networking is supported on Windows, macOS and Linux")

    run('emulation CreateSwitch "network-switch"')
    run('connector Connect sysbus.ethernet network-switch')
    run('connector Connect host.network network-switch')
