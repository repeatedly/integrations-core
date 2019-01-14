# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.sql.rtn.doc/doc/r0060769.html
OVERVIEW = """\
SELECT appls_cur_cons,
       connections_top,
       db_status,
       deadlocks,
       lock_wait_time,
       lock_waits,
       num_locks_held,
       num_locks_waiting
FROM TABLE(MON_GET_DATABASE(-2))
"""
