#include <helium/net_init.h>
#include <zephyr/kernel.h>

#include "server.h"

LOG_MODULE_REGISTER(osprey, LOG_LEVEL_INF);

int main(void) {
    int err = net_init(3000);
    if (err != 0) {
        LOG_ERR("Network initialization failed: %d", err);
        return err;
    }

    UA_StatusCode status = server_init();
    if (status != UA_STATUSCODE_GOOD) {
        LOG_ERR("OPC UA server failed: %s (0x%08x)", UA_StatusCode_name(status),
                (unsigned int)status);
        return -1;
    }
    return 0;
}
