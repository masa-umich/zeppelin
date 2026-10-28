# Osprey
This is an open62541 template / example project for you to reference when writing firmware for other MASA boards.

## Testing
Build for STM32 target with
```bash
just build osprey-app
```
Run a sim with
```bash
just sim run osprey-app
```
Just make sure you have podman installed. Also, to check that the network simulation reaches the outside you should try to connect to the server using Synnax. The only non-default connection setting you'll need is to change the address to `opc.tcp://127.0.0.1:4840` instead of localhost.

## Using in other projects
The major thing you'll need to replicate is the `CMakeLists.txt` file. This grabs and links the actual open62541 repository and patches it with some necessary fixes.

I've also not actually optimized the memory layout for a real STM32H725ZGT6 chip / board. You may need to move some sections around to make it all fit outside of a simulation.
