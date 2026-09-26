#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

// This is the real upstream umbrella header, with every client API included.
#include "client/cpp/synnax.h"

static int bring_up() {
    try {
        synnax::Config config;
        config.host = "192.168.1.1";
        config.secure = false;

        // Exercise real protobuf serialization, not just an include-only check.
        grpc::auth::LoginRequest request;
        request.set_username(config.username);
        request.set_password(config.password);
        std::string wire;
        if (!request.SerializeToString(&wire)) return 1;
        grpc::auth::LoginRequest decoded;
        if (!decoded.ParseFromString(wire) || decoded.username() != config.username)
            return 1;

        printk("Osprey: Synnax %s master header and protobuf ready (%u bytes)\n",
               SYNNAX_CLIENT_VERSION, static_cast<unsigned>(wire.size()));
#if defined(OSPREY_SYNNAX_FULL_CLIENT)
        synnax::Synnax client(config);
        const auto error = client.auth->authenticate();
        if (error) {
            printk("Synnax login failed: %s\n", error.message().c_str());
            return 1;
        }
        printk("Connected directly to Synnax.\n");
#else
        printk("Header smoke build: no connection is opened.\n");
#endif
    } catch (const std::exception& error) {
        printk("Synnax bring-up failed: %s\n", error.what());
        return 1;
    }
    return 0;
}

int main() {
    // Zephyr's native main thread has no pthread-specific key storage. Run
    // the client in a real POSIX thread, as required by gRPC and Abseil.
    int result = 1;
    try {
        std::thread client_thread([&result] { result = bring_up(); });
        client_thread.join();
    } catch (const std::exception& error) {
        printk("Could not start Synnax thread: %s\n", error.what());
    }
    return result;
}
