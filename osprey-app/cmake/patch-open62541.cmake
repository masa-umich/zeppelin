# Compatibility workaround for open62541 v1.5.8 and newer Zephyr releases:
# Zephyr exposes zsock_fd_set as a typedef of struct zvfs_fd_set, while this
# open62541 release refers to the old struct tag. Upstream fixed this in
# https://github.com/open62541/open62541/commit/938fcc5
# Remove this patch when updating to a release that contains that commit.
set(header "${OPEN62541_SOURCE_DIR}/arch/zephyr/eventloop_zephyr.h")
file(READ "${header}" contents)
set(old "typedef struct zsock_fd_set UA_fd_set;")
set(new "typedef zsock_fd_set UA_fd_set;")
string(FIND "${contents}" "${old}" position)
if(NOT position EQUAL -1)
    string(REPLACE "${old}" "${new}" contents "${contents}")
    file(WRITE "${header}" "${contents}")
else()
    string(FIND "${contents}" "${new}" position)
    if(position EQUAL -1)
        message(FATAL_ERROR
            "Unexpected open62541 socket type; "
            "review the Zephyr compatibility patch"
        )
    endif()
endif()
