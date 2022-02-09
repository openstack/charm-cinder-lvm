# Copyright 2019
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import charms_openstack.charm
import charms.reactive

from charmhelpers.contrib.openstack.utils import os_release
from charmhelpers.core.hookenv import (
    leader_get,
    leader_set,
    log,
)
from charmhelpers.fetch.ubuntu import (get_installed_version,
                                       apt_mark)
# This charm's library contains all of the handler code associated with
# this charm -- we will use the auto-discovery feature of charms.openstack
# to get the definitions for the charm.
import charms_openstack.bus
charms_openstack.bus.discover()

charms_openstack.charm.use_defaults(
    'charm.installed',
    'update-status',
    'upgrade-charm',
    'storage-backend.connected',
)


@charms.reactive.when('config.changed.driver-source')
def reinstall():
    with charms_openstack.charm.provide_charm_instance() as charm:
        charm.install()


@charms.reactive.when('leadership.is_leader')
@charms.reactive.when_any('charm.installed', 'upgrade-charm',
                          'storage-backend.connected')
def set_target_helper():
    log("Setting target-helper: {}".format(leader_get('target-helper')),
        "DEBUG")

    if leader_get('target-helper') is None:
        # For deployments upgrading from Victoria, we set the target helper
        # to the legacy default of tgtadm. For new deployments, lioadm. See
        # LP#1949074 for more details.
        if os_release('cinder-common') <= 'victoria':
            leader_set(settings={"target-helper": "tgtadm",
                                 "target-port": 3260})
            # Mark tgt as manual to prevent it from being removed. Since
            # Wallaby tgt is no longer a dependency of cinder-volume package
            # but some backends will still use it.
            if get_installed_version("tgt"):
                apt_mark("tgt", "manual")
        else:
            leader_set(settings={"target-helper": "lioadm",
                                 "target-port": 3260})

        log("Setting target-helper/port: {}/{}".format(
            leader_get('target-helper'), leader_get('target-port')),
            "DEBUG")
