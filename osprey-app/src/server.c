#include "server.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>

LOG_MODULE_REGISTER(opcua, LOG_LEVEL_INF);

struct led_channel {
    struct gpio_dt_spec gpio;
    char* name;
};

static struct led_channel leds[] = {
    {GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios), "led.green"},
    {GPIO_DT_SPEC_GET(DT_ALIAS(led1), gpios), "led.yellow"},
    {GPIO_DT_SPEC_GET(DT_ALIAS(led2), gpios), "led.red"},
};
static const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
static UA_Boolean button_toggle;
static int button_candidate;
static int button_stable;
static int64_t button_changed_at;

static UA_StatusCode read_channel(UA_Server* server, const UA_NodeId* session_id,
                                  void* session_context, const UA_NodeId* node_id,
                                  void* node_context, UA_Boolean timestamp,
                                  const UA_NumericRange* range, UA_DataValue* value) {
    if (range != NULL) {
        value->hasStatus = true;
        value->status = UA_STATUSCODE_BADINDEXRANGEINVALID;
        return UA_STATUSCODE_GOOD;
    }

    UA_Boolean state = button_toggle;
    if (node_context != NULL) {
        struct led_channel* led = node_context;
        int level = gpio_pin_get_dt(&led->gpio);
        if (level < 0) {
            value->hasStatus = true;
            value->status = UA_STATUSCODE_BADRESOURCEUNAVAILABLE;
            return UA_STATUSCODE_GOOD;
        }
        state = level != 0;
    }
    UA_StatusCode status =
        UA_Variant_setScalarCopy(&value->value, &state, &UA_TYPES[UA_TYPES_BOOLEAN]);
    if (status != UA_STATUSCODE_GOOD) return status;
    value->hasValue = true;
    if (timestamp) {
        value->hasSourceTimestamp = true;
        value->sourceTimestamp = UA_DateTime_now();
    }
    return UA_STATUSCODE_GOOD;
}

static UA_StatusCode write_led(UA_Server* server, const UA_NodeId* session_id,
                               void* session_context, const UA_NodeId* node_id,
                               void* node_context, const UA_NumericRange* range,
                               const UA_DataValue* value) {
    if (range != NULL) return UA_STATUSCODE_BADINDEXRANGEINVALID;
    if (!value->hasValue ||
        !UA_Variant_hasScalarType(&value->value, &UA_TYPES[UA_TYPES_BOOLEAN])) {
        return UA_STATUSCODE_BADTYPEMISMATCH;
    }
    struct led_channel* led = node_context;
    int err = gpio_pin_set_dt(&led->gpio, *(UA_Boolean*)value->value.data);
    return err == 0 ? UA_STATUSCODE_GOOD : UA_STATUSCODE_BADRESOURCEUNAVAILABLE;
}

/* Run on the server thread: GPIO sampling needs no ISR, workqueue or extra stack. */
static void sample_button(UA_Server* server, void* context) {
    int pressed = gpio_pin_get_dt(&button);
    if (pressed < 0) return;

    int64_t now = k_uptime_get();
    if (pressed != button_candidate) {
        button_candidate = pressed;
        button_changed_at = now;
    } else if (pressed != button_stable && now - button_changed_at >= 30) {
        button_stable = pressed;
        if (pressed) button_toggle = !button_toggle;
    }
}

static UA_StatusCode add_channel(UA_Server* server, char* name,
                                 struct led_channel* led) {
    UA_VariableAttributes attr = UA_VariableAttributes_default;
    attr.displayName = UA_LOCALIZEDTEXT("en-US", name);
    attr.dataType = UA_TYPES[UA_TYPES_BOOLEAN].typeId;
    attr.valueRank = UA_VALUERANK_SCALAR;
    attr.accessLevel = UA_ACCESSLEVELMASK_READ;
    if (led != NULL) attr.accessLevel |= UA_ACCESSLEVELMASK_WRITE;

    UA_CallbackValueSource source = {.read = read_channel,
                                     .write = led != NULL ? write_led : NULL};
    return UA_Server_addCallbackValueSourceVariableNode(
        server, UA_NODEID_STRING(1, name), UA_NODEID_NUMERIC(0, UA_NS0ID_OBJECTSFOLDER),
        UA_NODEID_NUMERIC(0, UA_NS0ID_ORGANIZES), UA_QUALIFIEDNAME(1, name),
        UA_NODEID_NUMERIC(0, UA_NS0ID_BASEDATAVARIABLETYPE), attr, source, led, NULL);
}

UA_StatusCode server_init(void) {
    for (size_t i = 0; i < ARRAY_SIZE(leds); ++i) {
        if (!gpio_is_ready_dt(&leds[i].gpio) ||
            gpio_pin_configure_dt(&leds[i].gpio, GPIO_OUTPUT_INACTIVE) != 0) {
            return UA_STATUSCODE_BADRESOURCEUNAVAILABLE;
        }
    }
    if (!gpio_is_ready_dt(&button) || gpio_pin_configure_dt(&button, GPIO_INPUT) != 0) {
        return UA_STATUSCODE_BADRESOURCEUNAVAILABLE;
    }
    int pressed = gpio_pin_get_dt(&button);
    if (pressed < 0) return UA_STATUSCODE_BADRESOURCEUNAVAILABLE;
    button_candidate = button_stable = pressed;
    button_changed_at = k_uptime_get();
    button_toggle = false;

    /* Keep the large configuration off the main thread's stack. */
    static UA_ServerConfig config;
    memset(&config, 0, sizeof(config));
    UA_StatusCode status =
        UA_ServerConfig_setMinimalCustomBuffer(&config, 4840, NULL, 8192, 8192);
    if (status != UA_STATUSCODE_GOOD) {
        UA_ServerConfig_clear(&config);
        return status;
    }
    config.tcpMaxMsgSize = 8192;
    config.tcpMaxChunks = 1;
    config.maxSecureChannels = 1;
    config.maxSessions = 1;
    config.maxNodesPerRead = 4;
    config.maxNodesPerWrite = 3;
    UA_Server* server = UA_Server_newWithConfig(&config);
    if (server == NULL) return UA_STATUSCODE_BADOUTOFMEMORY;

    for (size_t i = 0; i < ARRAY_SIZE(leds); ++i) {
        status = add_channel(server, leds[i].name, &leds[i]);
        if (status != UA_STATUSCODE_GOOD) goto cleanup;
    }
    status = add_channel(server, "button.toggle", NULL);
    if (status != UA_STATUSCODE_GOOD) goto cleanup;
    status = UA_Server_addRepeatedCallback(server, sample_button, NULL, 10, NULL);
    if (status != UA_STATUSCODE_GOOD) goto cleanup;

    LOG_INF("OPC UA ready: led.green, led.yellow, led.red, button.toggle (ns=1)");
    volatile UA_Boolean running = true;
    status = UA_Server_run(server, &running);

cleanup:
    UA_Server_delete(server);
    return status;
}
