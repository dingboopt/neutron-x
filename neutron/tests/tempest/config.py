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

from oslo_config import cfg

from tempest import config

CONF = config.CONF


NeutronPluginOptions = [
    cfg.BoolOpt('specify_floating_ip_address_available',
                default=True,
                help='Allow passing an IP Address of the floating ip when '
                     'creating the floating ip')]

# TODO(amuller): Redo configuration options registration as part of the planned
# transition to the Tempest plugin architecture
for opt in NeutronPluginOptions:
    CONF.register_opt(opt, 'neutron_plugin_options')
