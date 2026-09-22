#include <helium/net_init.h>
#include <zephyr/kernel.h>
#include "server.h"

int main(void) {
    net_init(3000);
    
    server_init();
    return 0;
}
