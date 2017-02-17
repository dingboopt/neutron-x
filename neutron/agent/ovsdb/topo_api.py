# Copyright (c) 2014 OpenStack Foundation
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

import abc
import collections
import uuid

from oslo_config import cfg
from oslo_utils import importutils
import six

from neutron._i18n import _

interface_map = {
    'native': 'neutron.agent.ovsdb.impl_topo_idl.OvsdbTopoIdl',
}

OPTS = [
    cfg.StrOpt('ovsdb_topo_interface',
               choices=interface_map.keys(),
               default='native',
               help=_('The interface for interacting with the OVSDB TOPO')),
    cfg.StrOpt('ovsdb_topo_connection',
               default='tcp:127.0.0.1:6641',
               help=_('The connection string for the native OVSDBTOPO backend. '
                      'Requires the native ovsdb_interface to be enabled.'))
]
cfg.CONF.register_opts(OPTS, 'OVS')


@six.add_metaclass(abc.ABCMeta)
class Command(object):
    """An OVSDB command that can be executed in a transaction

    :attr result: The result of executing the command in a transaction
    """

    @abc.abstractmethod
    def execute(self, **transaction_options):
        """Immediately execute an OVSDB command

        This implicitly creates a transaction with the passed options and then
        executes it, returning the value of the executed transaction

        :param transaction_options: Options to pass to the transaction
        """


@six.add_metaclass(abc.ABCMeta)
class Transaction(object):
    @abc.abstractmethod
    def commit(self):
        """Commit the transaction to OVSDB"""

    @abc.abstractmethod
    def add(self, command):
        """Append an OVSDB operation to the transaction"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, tb):
        if exc_type is None:
            self.result = self.commit()


@six.add_metaclass(abc.ABCMeta)
class API(object):
    def __init__(self, context):
        self.context = context

    @staticmethod
    def get(context, iface_name=None):
        """Return the configured OVSDB API implementation"""
        iface = importutils.import_class(
            interface_map[iface_name or cfg.CONF.OVS.ovsdb_topo_interface])
        return iface(context)

    @abc.abstractmethod
    def transaction(self, check_error=False, log_errors=True, **kwargs):
        """Create a transaction

        :param check_error: Allow the transaction to raise an exception?
        :type check_error:  bool
        :param log_errors:  Log an error if the transaction fails?
        :type log_errors:   bool
        :returns: A new transaction
        :rtype: :class:`Transaction`
        """

    @abc.abstractmethod
    def db_create(self, table, **col_values):
        """Create a command to create new record

        :param table:      The OVS table containing the record to be created
        :type table:       string
        :param col_values: The columns and their associated values
                           to be set after create
        :type col_values:  Dictionary of columns id's and values
        :returns:          :class:`Command` with no result
        """

