# Copyright (c) 2015 Red Hat, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from ovs.db import idl
from six.moves import queue as Queue

from neutron._i18n import _
from neutron.agent.ovsdb import topo_api
from neutron.agent.ovsdb.native import topo_commands as cmd
from neutron.agent.ovsdb.native import connection
from neutron.agent.ovsdb.native import idlutils


cfg.CONF.import_opt('ovs_vsctl_timeout', 'neutron.agent.common.ovs_lib')

LOG = logging.getLogger(__name__)


class Transaction(topo_api.Transaction):
    def __init__(self, api, ovsdb_connection, timeout,
                 check_error=False, log_errors=False):
        self.api = api
        self.check_error = check_error
        self.log_errors = log_errors
        self.commands = []
        self.results = Queue.Queue(1)
        self.ovsdb_connection = ovsdb_connection
        self.timeout = timeout

    def add(self, command):
        """Add a command to the transaction

        returns The command passed as a convenience
        """

        self.commands.append(command)
        return command

    def commit(self):
        self.ovsdb_connection.queue_txn(self)
        result = self.results.get()
        if self.check_error:
            if isinstance(result, idlutils.ExceptionResult):
                if self.log_errors:
                    LOG.error(result.tb)
                raise result.ex
        return result

    def do_commit(self):
        start_time = time.time()
        attempts = 0
        while True:
            elapsed_time = time.time() - start_time
            if attempts > 0 and elapsed_time > self.timeout:
                raise RuntimeError("OVS transaction timed out")
            attempts += 1
            # TODO(twilson) Make sure we don't loop longer than vsctl_timeout
            txn = idl.Transaction(self.api.idl)
            for i, command in enumerate(self.commands):
                LOG.debug("Running txn command(idx=%(idx)s): %(cmd)s",
                          {'idx': i, 'cmd': command})
                try:
                    command.run_idl(txn)
                except Exception:
                    with excutils.save_and_reraise_exception() as ctx:
                        txn.abort()
                        if not self.check_error:
                            ctx.reraise = False
            seqno = self.api.idl.change_seqno
            status = txn.commit_block()
            if status == txn.TRY_AGAIN:
                LOG.debug("OVSDB transaction returned TRY_AGAIN, retrying")
                idlutils.wait_for_change(
                    self.api.idl, self.timeout - elapsed_time,
                    seqno)
                continue
            elif status == txn.ERROR:
                msg = _("OVSDB Error: %s") % txn.get_error()
                if self.log_errors:
                    LOG.error(msg)
                if self.check_error:
                    # For now, raise similar error to vsctl/utils.execute()
                    raise RuntimeError(msg)
                return
            elif status == txn.ABORTED:
                LOG.debug("Transaction aborted")
                return
            elif status == txn.UNCHANGED:
                LOG.debug("Transaction caused no change")

            return [cmd.result for cmd in self.commands]


class OvsdbTopoIdl(topo_api.API):

    ovsdb_connection = connection.Connection(cfg.CONF.OVS.ovsdb_topo_connection,
                                             cfg.CONF.ovs_vsctl_timeout,
                                             'Topo')

    def __init__(self, context):
        super(OvsdbTopoIdl, self).__init__(context)
        OvsdbTopoIdl.ovsdb_connection.start()
        self.idl = OvsdbTopoIdl.ovsdb_connection.idl

    @property
    def _tables(self):
        return self.idl.tables

    def transaction(self, check_error=False, log_errors=True, **kwargs):
        return Transaction(self, OvsdbTopoIdl.ovsdb_connection,
                           self.context.vsctl_timeout,
                           check_error, log_errors)

    def update_net(self, net_uuid, tenant, data):
        return cmd.UpdateNetCommand(self,net_uuid, tenant, data)

    def update_port(self, port_uuid, tenant, data, fixed_ips):
        return cmd.UpdatePortCommand(self,port_uuid, tenant, data, fixed_ips)

    def get_port(self, port_uuid):
        return cmd.GetPortCommand(self,port_uuid)

    def get_port_details(self, port_uuid):
        return cmd.GetPortDetailsCommand(self,port_uuid)

    def db_create(self, table, **col_values):
        return cmd.DbCreateCommand(self, table, **col_values)

