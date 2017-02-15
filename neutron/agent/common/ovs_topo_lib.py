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
    
    def update_net(self, net_uuid, tenant, data):
        return self.ovsdb.update_net(net_uuid, tenant, data).execute()

    def update_port(self, net_uuid, tenant, data, fixed_ips):
        return self.ovsdb.update_port(net_uuid, tenant, data, fixed_ips).execute()

    def get_port(self, port_uuid):
        return self.ovsdb.get_port(port_uuid).execute()

    def db_create(self, table, **col_values):
        return self.ovsdb.db_create(table, **col_values).execute()

