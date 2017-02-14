# Copyright (c) 2015 OpenStack Foundation
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

import collections

from oslo_log import log as logging
from oslo_utils import excutils

from neutron._i18n import _, _LE
from neutron.agent.ovsdb import topo_api
from neutron.agent.ovsdb.native import idlutils

LOG = logging.getLogger(__name__)


class BaseCommand(topo_api.Command):
    def __init__(self, api):
        self.api = api
        self.result = None

    def execute(self, check_error=False, log_errors=True):
        try:
            with self.api.transaction(check_error, log_errors) as txn:
                txn.add(self)
            return self.result
        except Exception:
            with excutils.save_and_reraise_exception() as ctx:
                if log_errors:
                    LOG.exception(_LE("Error executing command"))
                if not check_error:
                    ctx.reraise = False

    def __str__(self):
        command_info = self.__dict__
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join("%s=%s" % (k, v) for k, v in command_info.items()
                      if k not in ['api', 'result']))


class DbCreateCommand(BaseCommand):
    def __init__(self, api, table, **columns):
        super(DbCreateCommand, self).__init__(api)
        self.table = table
        self.columns = columns

    def run_idl(self, txn):
        row = txn.insert(self.api._tables[self.table])
        for col, val in self.columns.items():
            setattr(row, col, val)
        self.result = row



class GetPortCommand(BaseCommand):
    def __init__(self, api, port_uuid):
        super(GetPortCommand, self).__init__(api)
        self.port_uuid = port_uuid

    def run_idl(self, txn):
        port = idlutils.row_by_value(self.api.idl, 'Port', 'port_uuid', self.port_uuid, None)
        return port

class UpdatePortCommand(BaseCommand):
    def __init__(self, api, port_uuid):
        super(UpdatePortCommand, self).__init__(api, port_uuid)
        self.port_uuid = port_uuid

    def run_idl(self, txn):
        br = idlutils.row_by_value(self.api.idl, 'Port', 'uuid', self.port_uuid)
        br.verify('controller')
