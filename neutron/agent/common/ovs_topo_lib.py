# Copyright 2011 VMware, Inc.
# All Rights Reserved.
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
import itertools
import operator
import time
import uuid

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
import retrying
import six

from neutron._i18n import _, _LE, _LI, _LW
from neutron.agent.common import utils
from neutron.agent.linux import ip_lib
from neutron.agent.ovsdb import topo_api as ovstopo
from neutron.common import exceptions
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2.drivers.openvswitch.agent.common \
    import constants

UINT64_BITMASK = (1 << 64) - 1

# Default timeout for ovs-vsctl command
DEFAULT_OVS_VSCTL_TIMEOUT = 10

# Special return value for an invalid OVS ofport
INVALID_OFPORT = -1
UNASSIGNED_OFPORT = []

# OVS bridge fail modes
FAILMODE_SECURE = 'secure'
FAILMODE_STANDALONE = 'standalone'

OPTS = [
    cfg.IntOpt('ovs_vsctl_timeout',
               default=DEFAULT_OVS_VSCTL_TIMEOUT,
               help=_('Timeout in seconds for ovs-vsctl commands. '
                      'If the timeout expires, ovs commands will fail with '
                      'ALARMCLOCK error.')),
]
cfg.CONF.register_opts(OPTS)

LOG = logging.getLogger(__name__)


class OVSTopo(object):

    def __init__(self):
        self.vsctl_timeout = cfg.CONF.ovs_vsctl_timeout
        self.ovsdb = ovstopo.API.get(self)

    def update_port(self, port_uuid):
        self.ovsdb.update_port(port_uuid).execute()

    def delete_bridge(self, bridge_name):
        self.ovsdb.del_br(bridge_name).execute()

    def bridge_exists(self, bridge_name):
        return self.ovsdb.br_exists(bridge_name).execute()

    def port_exists(self, port_name):
        cmd = self.ovsdb.db_get('Port', port_name, 'name')
        return bool(cmd.execute(check_error=False, log_errors=False))

    def get_bridge_for_iface(self, iface):
        return self.ovsdb.iface_to_br(iface).execute()

    def get_bridges(self):
        return self.ovsdb.list_br().execute(check_error=True)

    def get_bridge_external_bridge_id(self, bridge):
        return self.ovsdb.br_get_external_id(bridge, 'bridge-id').execute()

    def set_db_attribute(self, table_name, record, column, value,
                         check_error=False, log_errors=True):
        self.ovsdb.db_set(table_name, record, (column, value)).execute(
            check_error=check_error, log_errors=log_errors)

    def clear_db_attribute(self, table_name, record, column):
        self.ovsdb.db_clear(table_name, record, column).execute()

    def db_get_val(self, table, record, column, check_error=False,
                   log_errors=True):
        return self.ovsdb.db_get(table, record, column).execute(
            check_error=check_error, log_errors=log_errors)
