#include "server.h"

LOG_MODULE_REGISTER();

UA_StatusCode server_init(void) {
    static UA_ServerConfig config;
    memset(&config, 0, sizeof(UA_ServerConfig));
    UA_ServerConfig_setDefault(&config);
    // Minimum is 8192
    config.tcpBufSize = 1 << 13;
    config.tcpMaxMsgSize = 1 << 13;
    config.maxSecureChannels = 1;
    config.maxSessions = 1;
    UA_Server *server = UA_Server_newWithConfig(&config);
    if (server == NULL) {
      LOG_ERR("UA_Server_new failed");
      return EXIT_FAILURE;
    }

    // Add a variable node to the adresspace
    UA_VariableAttributes attr; attr = UA_VariableAttributes_default;
    UA_Int32 myInteger; myInteger = 42;
    UA_Variant_setScalarCopy(&attr.value, &myInteger, &UA_TYPES[UA_TYPES_INT32]);
    attr.description = UA_LOCALIZEDTEXT_ALLOC("en-US", "the answer");
    attr.displayName = UA_LOCALIZEDTEXT_ALLOC("en-US", "the answer");
    UA_NodeId myIntegerNodeId; myIntegerNodeId = UA_NODEID_STRING_ALLOC(1, "the.answer");
    UA_QualifiedName myIntegerName; myIntegerName = UA_QUALIFIEDNAME_ALLOC(1, "the answer");
    UA_NodeId parentNodeId; parentNodeId = UA_NODEID_NUMERIC(0, UA_NS0ID_OBJECTSFOLDER);
    UA_NodeId parentReferenceNodeId; parentReferenceNodeId = UA_NODEID_NUMERIC(0, UA_NS0ID_ORGANIZES);
    UA_Server_addVariableNode(server, myIntegerNodeId, parentNodeId,
                              parentReferenceNodeId, myIntegerName,
                              UA_NODEID_NULL, attr, NULL, NULL);

    // /* Allocations on the heap need to be freed */
    UA_VariableAttributes_clear(&attr);
    UA_NodeId_clear(&myIntegerNodeId);
    UA_QualifiedName_clear(&myIntegerName);

    volatile UA_Boolean running = true;
    UA_StatusCode retval = UA_Server_run(server, &running);

    UA_Server_delete(server);
    return retval;
}
