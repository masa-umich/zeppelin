# Renode Simulation
This is the remenants of the currently un-maintained renode simulation for this repository. Below is a background of what renode is and why it's been somewhat abanadoned as of now, but might be useful later which is why it's still in this repository.

# Background 
So I've been trying to setup some sort of simulation for Zeppelin where we could run the Open62541 (OPC UA) server and have it communicate to a local Synnax cluster to verify functionality without any real hardware but I've run into some snags. There are three potential ways of doing this:
- Using Zephyr's "native_sim" target
  - Pros: Very simple, I've tried this and it works perfectly, all you need is a separate .conf file for the native_sim target and run it in NSOS mode to do network bridging.
  - Cons: Only works on Linux, so for cross-compatibility we'd need to make Docker/Podman a requirement. It also skips actually simulating the hardware limitations and interactions so it won't catch things like running out of stack memory or interacting with the actual ethernet PHY. 
- Using Renode
  - Pros: Does very low-level hardware emulation, to the point that you literally load the exact .elf file you'd flash on a microcontroller and it'll remap all of the register read/writes on the fly. This allows you to not only verify that all of your hardware drivers work, but even theoretically allows emulation of off-chip peripherals. You can also use it programmatically with Python so things like unit tests in CI would be a piece of cake.
  - Cons: The setup is very difficult and while I tried my best to make a justfile to handle the setup, there is still a lot of manual configuration required and other dependencies needed. It also seems like due to a bug in Renode it is either impossible or very difficult to do network bridging with the host, although device-to-device ethernet networking is probably fine. 
- Using QEMU
  - Pros: It is similar to Renode in that you can load the real firmware files you'd flash onto a board, and it is a more industry standard tool than Renode and so (although I haven't tried) network bridging is likely possible. It's also cross-platform and seems much easier to setup than Renode (again, I haven't tried though)
  - Cons: QEMU simply doesn't support the ARM-M7 architecture that our STM chips use, and there is no presets I can find for the STM32H7 series chips, meaning that making a one-to-one simulation would be extremely difficult. We may be able to get around this by building for a different STM target which there are existing presets for, but that's obviously not very ideal and may introduce more parity issues.
  - Note: I haven't actually tried this approach because of the aforementioned lack of good presets for STM chips so I don't really know what implementing this would look like.

I think the best path forward will be to use native_sim with Podman/Docker as a new dependency of Zeppelin to run "interactive" tests, this should also work if we choose to do automated testing because CI already happens inside of containers and I think has good Twister/ZTest support.

Then, if in the future we want to do simulation of off-chip peripherals, or just want to do more "real" software-in-the-loop testing, we can go back to Renode (probably also in Podman/Docker to simplify setup), but at the moment I don't think there's a good reason to open that can of worms when there are alternatives.