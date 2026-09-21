#include <open62541/server.h>
#include <open62541/server_config_default.h>

#include "zephyr/sys/printk.h"

int main(void) {
    printk("Hello");
    return 0;
}
