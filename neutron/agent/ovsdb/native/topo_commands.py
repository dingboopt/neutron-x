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

class UpdateNetCommand(BaseCommand):
    def __init__(self, api,net_uuid, tenant, data):
        super(UpdateNetCommand, self).__init__(api)
        self.net_uuid = net_uuid
        self.tenant = tenant
        self.data = data

    def run_idl(self, txn):
        net = idlutils.row_by_value(self.api.idl, 'Network', 'network_uuid', self.net_uuid, None)
        if net is None:
            net = txn.insert(self.api._tables['Network'])
            
        net.network_uuid = self.net_uuid
        net.tenant = self.tenant
        net.data = self.data

class GetPortCommand(BaseCommand):
    def __init__(self, api, port_uuid):
        super(GetPortCommand, self).__init__(api)
        self.port_uuid = port_uuid

    def run_idl(self, txn):
        port = idlutils.row_by_value(self.api.idl, 'Port', 'port_uuid', self.port_uuid, None)
        self.result = port

class GetPortDetailsCommand(BaseCommand):
    def __init__(self, api, port_uuid):
        super(GetPortDetailsCommand, self).__init__(api)
        self.port_uuid = port_uuid

    def run_idl(self, txn):
        port = idlutils.row_by_value(self.api.idl, 'Port', 'port_uuid', self.port_uuid, None)
        if port is None:
            return None
        net_id = port.data['network_id']
        net = idlutils.row_by_value(self.api.idl, 'Network', 'network_uuid', net_id, None)
        if net is None:
            return None
        fixed_ips = []
        for ip in port.fixed_ips.keys():
            fixed_ips.append({'subnet_id': port.fixed_ips[ip], 'ip':ip})
        entry = {'device': self.port_uuid,
         'network_id': port.data['network_id'],
         'port_id': self.port_uuid,
         'mac_address': port.data['mac_address'],
         'admin_state_up': True if port.data['admin_state_up'] ==  'True' else False,
         'network_type': net.data['provider:network_type'],
         'segmentation_id': int(net.data['provider:segmentation_id']),
         'physical_network': None if net.data['provider:physical_network'] == 'None' else net.data['provider:physical_network'],
         'fixed_ips': fixed_ips,
         'device_owner': port.data['device_owner'],
         'allowed_address_pairs': [],
         'port_security_enabled': False,
         'qos_policy_id': None,
         'network_qos_policy_id': None,
         #'security_groups':port['security_groups'],
         'profile': {}}
        self.result = entry

class UpdatePortCommand(BaseCommand):
    def __init__(self, api,port_uuid, tenant, data, fixed_ips):
        super(UpdatePortCommand, self).__init__(api)
        self.port_uuid = port_uuid
        self.tenant = tenant
        self.data = data
        self.fixed_ips = fixed_ips

    def run_idl(self, txn):
        port = idlutils.row_by_value(self.api.idl, 'Port', 'port_uuid', self.port_uuid, None)
        if port is None:
            port = txn.insert(self.api._tables['Port'])
            
        port.port_uuid = self.port_uuid
        port.tenant = self.tenant
        port.data = self.data
        port.fixed_ips = self.fixed_ips

class UpdateSgruleCommand(BaseCommand):
    def __init__(self, api,sgrule_id, security_group_id, tenant_id, description, port_range_min,
                         port_range_max, remote_group_id, direction, ethertype, remote_ip_prefix, protocol):
        super(UpdateSgruleCommand, self).__init__(api)
        self.sgrule_id = sgrule_id
        self.security_group_id = security_group_id
        self.tenant_id = tenant_id
        self.description = description
        self.port_range_min = port_range_min
        self.port_range_max = port_range_max
        self.remote_group_id = remote_group_id
        self.direction = direction
        self.ethertype = ethertype
        self.remote_ip_prefix = remote_ip_prefix
        self.protocol = protocol

    def run_idl(self, txn):
        sgrule = idlutils.row_by_value(self.api.idl, 'Sgrule', 'sgrule_uuid', self.sgrule_id, None)
        if sgrule is None:
            sgrule = txn.insert(self.api._tables['Sgrule'])
            
        sgrule.sgrule_uuid = self.sgrule_id
        sgrule.sg_uuid = self.security_group_id
        sgrule.tenant_id = self.tenant_id
        sgrule.description = self.description
        sgrule.port_range_min = self.port_range_min
        sgrule.port_range_max = self.port_range_max
        sgrule.remote_group_id = self.remote_group_id
        sgrule.direction = self.direction 
        sgrule.ethertype = self.ethertype 
        sgrule.remote_ip_prefix = self.remote_ip_prefix
        sgrule.protocol = self.protocol
