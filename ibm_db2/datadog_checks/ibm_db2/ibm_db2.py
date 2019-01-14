# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from __future__ import division

import ibm_db

from datadog_checks.base import AgentCheck
from datadog_checks.base.utils.containers import hash_mutable
from .utils import scrub_connection_string, status_to_service_check
from . import queries


class IbmDb2Check(AgentCheck):
    METRIC_PREFIX = 'ibm_db2'
    SERVICE_CHECK_CONNECT = '{}.can_connect'.format(METRIC_PREFIX)
    SERVICE_CHECK_STATUS = '{}.status'.format(METRIC_PREFIX)

    def __init__(self, name, init_config, agentConfig, instances=None):
        super(IbmDb2Check, self).__init__(name, init_config, agentConfig, instances)
        self._config_cache = {}

    def check(self, instance):
        config = self.get_config(instance)
        if config is None:
            return

        self.query_overview(config)

    def query_overview(self, config):
        statement = ibm_db.exec_immediate(config['connection'], queries.OVERVIEW)
        result = ibm_db.fetch_assoc(statement)

        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0001156.html
        self.service_check(self.SERVICE_CHECK_STATUS, status_to_service_check(result['db_status']), tags=config['tags'])

        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0001201.html
        self.gauge(self.m('applications.active'), result['appls_cur_cons'], tags=config['tags'])

        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0002225.html
        self.monotonic_count(self.m('connections.max'), result['connections_top'], tags=config['tags'])

        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0001283.html
        self.monotonic_count(self.m('locks.dead'), result['deadlocks'], tags=config['tags'])

        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0001281.html
        self.gauge(self.m('locks.active'), result['num_locks_held'], tags=config['tags'])

        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0001296.html
        self.gauge(self.m('locks.waiting'), result['num_locks_waiting'], tags=config['tags'])

        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0001294.html
        # https://www.ibm.com/support/knowledgecenter/SSEPGG_11.1.0/com.ibm.db2.luw.admin.mon.doc/doc/r0001293.html
        if result['lock_waits']:
            average_lock_wait = result['lock_wait_time'] / result['lock_waits']
        else:
            average_lock_wait = 0
        self.gauge(self.m('locks.wait'), average_lock_wait, tags=config['tags'])

    def get_config(self, instance):
        instance_id = hash_mutable(instance)
        config = self._config_cache.get(instance_id)

        if config is None:
            config = {
                'db': instance.get('db', ''),
                'username': instance.get('username', ''),
                'password': instance.get('password', ''),
                'host': instance.get('host', ''),
                'port': instance.get('port', 5000),
                'tags': instance.get('tags', []),
            }
            config['tags'].append('db:{}'.format(config['db']))

            config['connection'] = self.get_connection(config)
            if not config['connection']:
                return

            self._config_cache[instance_id] = config

        return config

    def get_connection(self, config):
        target, username, password = self.get_connection_data(config)

        # Get column names in lower case
        connection_options = {ibm_db.ATTR_CASE: ibm_db.CASE_LOWER}

        try:
            connection = ibm_db.connect(target, username, password, connection_options)
        except Exception as e:
            if config['host']:
                self.log.error('Unable to connect with `{}`: {}'.format(scrub_connection_string(target), e))
            else:
                self.log.error('Unable to connect to database `{}` as user `{}`: {}'.format(target, username, e))
            self.service_check(self.SERVICE_CHECK_CONNECT, self.CRITICAL, tags=config['tags'])
        else:
            self.service_check(self.SERVICE_CHECK_CONNECT, self.OK, tags=config['tags'])
            return connection

    @classmethod
    def get_connection_data(cls, config):
        if config['host']:
            target = 'database={};hostname={};port={};protocol=tcpip;uid={};pwd={}'.format(
                config['db'], config['host'], config['port'], config['username'], config['password']
            )
            username = ''
            password = ''
        else:
            target = config['db']
            username = config['username']
            password = config['password']

        return target, username, password

    @classmethod
    def m(cls, metric):
        return '{}.{}'.format(cls.METRIC_PREFIX, metric)
