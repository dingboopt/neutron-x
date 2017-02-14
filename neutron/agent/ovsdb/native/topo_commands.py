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

class GetPortCommand(BaseCommand):
    def __init__(self, api, port_uuid):
        super(GetPortCommand, self).__init__(api)
        self.port_uuid = port_uuid

    def run_idl(self, txn):
        port = idlutils.row_by_value(self.api.idl, 'Port', 'uuid', self.port_uuid, None)
        return port

class UpdatePortCommand(BaseCommand):
    def __init__(self, api, port_uuid):
        super(UpdatePortCommand, self).__init__(api, port_uuid)
        self.port_uuid = port_uuid

    def run_idl(self, txn):
        br = idlutils.row_by_value(self.api.idl, 'Port', 'uuid', self.port_uuid)
        br.verify('controller')


class DbDestroyCommand(BaseCommand):
    def __init__(self, api, table, record):
        super(DbDestroyCommand, self).__init__(api)
        self.table = table
        self.record = record

    def run_idl(self, txn):
        record = idlutils.row_by_record(self.api.idl, self.table, self.record)
        record.delete()


class DbSetCommand(BaseCommand):
    def __init__(self, api, table, record, *col_values):
        super(DbSetCommand, self).__init__(api)
        self.table = table
        self.record = record
        self.col_values = col_values

    def run_idl(self, txn):
        record = idlutils.row_by_record(self.api.idl, self.table, self.record)
        for col, val in self.col_values:
            # TODO(twilson) Ugh, the OVS library doesn't like OrderedDict
            # We're only using it to make a unit test work, so we should fix
            # this soon.
            if isinstance(val, collections.OrderedDict):
                val = dict(val)
            setattr(record, col, val)


class DbClearCommand(BaseCommand):
    def __init__(self, api, table, record, column):
        super(DbClearCommand, self).__init__(api)
        self.table = table
        self.record = record
        self.column = column

    def run_idl(self, txn):
        record = idlutils.row_by_record(self.api.idl, self.table, self.record)
        # Create an empty value of the column type
        value = type(getattr(record, self.column))()
        setattr(record, self.column, value)


class DbGetCommand(BaseCommand):
    def __init__(self, api, table, record, column):
        super(DbGetCommand, self).__init__(api)
        self.table = table
        self.record = record
        self.column = column

    def run_idl(self, txn):
        record = idlutils.row_by_record(self.api.idl, self.table, self.record)
        # TODO(twilson) This feels wrong, but ovs-vsctl returns single results
        # on set types without the list. The IDL is returning them as lists,
        # even if the set has the maximum number of items set to 1. Might be
        # able to inspect the Schema and just do this conversion for that case.
        result = idlutils.get_column_value(record, self.column)
        if isinstance(result, list) and len(result) == 1:
            self.result = result[0]
        else:
            self.result = result

