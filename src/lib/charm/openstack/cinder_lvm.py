# Copyright 2021 Canonical Ltd
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


import subprocess
import socket

import charms_openstack.charm
import charmhelpers.core.hookenv as ch_hookenv  # noqa

from charmhelpers.core.strutils import (
    bytes_from_string,
)

from charmhelpers.core.host import (
    mounts,
    umount,
)

from charmhelpers.contrib.storage.linux.utils import (
    is_block_device,
    zap_disk,
    is_device_mounted,
)

from charmhelpers.contrib.storage.linux.loopback import (
    ensure_loopback_device,
)

from charmhelpers.contrib.storage.linux.lvm import (
    create_lvm_physical_volume,
    create_lvm_volume_group,
    deactivate_lvm_volume_group,
    extend_logical_volume_by_device,
    is_lvm_physical_volume,
    list_lvm_volume_group,
    list_thin_logical_volume_pools,
    remove_lvm_physical_volume,
)


charms_openstack.charm.use_defaults('charm.default-select-release')


DEFAULT_LOOPBACK_SIZE = '5G'
VOLUME_DRIVER = "cinder.volume.drivers.lvm.LVMVolumeDriver"
VOLUMES_DIR = "/var/lib/cinder/volumes"
VOLUME_NAME_TEMPLATE = "volume-%s"


def get_backend_name():
    hostname = socket.gethostname()
    alias = ch_hookenv.config('alias')
    unique_backend = ch_hookenv.config('unique-backend')

    if unique_backend is True:
        backend_name = 'LVM-{}-{}'.format(hostname, alias)
    else:
        backend_name = 'LVM-{}'.format(alias)

    return backend_name


def get_volume_group_name():
    return "cinder-volumes-{}".format(ch_hookenv.config('alias'))


def configure_block_devices():
    e_mountpoint = ch_hookenv.config('ephemeral-unmount')
    if e_mountpoint and filesystem_mounted(e_mountpoint):
        umount(e_mountpoint)

    conf = ch_hookenv.config()
    block_devices = []
    if conf['block-device'] not in [None, 'None', 'none']:
        block_devices.extend(conf['block-device'].split())
        ch_hookenv.status_set('maintenance',
                              'Checking configuration of lvm storage')
    # Note that there may be None now, and remove-missing is set to true,
    # so we still have to run the function regardless of whether
    # block_devices is an empty list or not.
    configure_lvm_storage(block_devices,
                          get_volume_group_name(),
                          conf['overwrite'],
                          conf['remove-missing'],
                          conf['remove-missing-force'])


def configure_lvm_storage(block_devices, volume_group, overwrite=False,
                          remove_missing=False, remove_missing_force=False):
    ''' Configure LVM storage on the list of block devices provided

    :param block_devices: list: List of allow-listed block devices to detect
                                and use if found
    :param overwrite: bool: Scrub any existing block data if block device is
                            not already in-use
    :param remove_missing: bool: Remove missing physical volumes from volume
                           group if logical volume not allocated on them
    :param remove_missing_force: bool: Remove missing physical volumes from
                           volume group even if logical volumes are allocated
                           on them. Overrides 'remove_missing' if set.
    '''
    juju_log('LVM info before preparation')
    log_lvm_info()

    juju_log('block_devices: {}'.format(','.join(block_devices)))

    devices = []
    for block_device in block_devices:
        (block_device, size) = _parse_block_device(block_device)

        if not is_device_mounted(block_device):
            if size == 0 and is_block_device(block_device):
                devices.append(block_device)
            elif size > 0:
                lo_device = ensure_loopback_device(block_device, str(size))
                devices.append(lo_device)

    juju_log('devices: {}'.format(','.join(devices)))

    vg_found = False
    new_devices = []
    for device in devices:
        if not is_lvm_physical_volume(device):
            # Unused device
            if overwrite is True or not has_partition_table(device):
                prepare_volume(device)
                new_devices.append(device)
        elif list_lvm_volume_group(device) != volume_group:
            # Existing LVM but not part of required VG or new device
            if overwrite is True:
                prepare_volume(device)
                new_devices.append(device)
        else:
            # Mark vg as found
            juju_log('Found volume-group already created on {}'.format(
                device))
            vg_found = True

    juju_log('new_devices: {}'.format(','.join(new_devices)))

    juju_log('LVM info mid preparation')
    log_lvm_info()

    if not vg_found and new_devices:
        if overwrite:
            ensure_lvm_volume_group_non_existent(volume_group)

        # Create new volume group from first device
        create_lvm_volume_group(volume_group, new_devices[0])
        new_devices.remove(new_devices[0])

    # Remove missing physical volumes from volume group
    try:
        if remove_missing_force:
            reduce_lvm_volume_group_missing(volume_group,
                                            extra_args=['--force'])
        elif remove_missing:
            reduce_lvm_volume_group_missing(volume_group)
    except subprocess.CalledProcessError as e:
        juju_log("reduce_lvm_volume_group_missing() didn't complete."
                 " LVM may not be fully configured yet.  Error was: '{}'."
                 .format(str(e)))

    if new_devices:
        # Extend the volume group as required
        for new_device in new_devices:
            extend_lvm_volume_group(volume_group, new_device)
            thin_pools = list_thin_logical_volume_pools(path_mode=True)
            if not thin_pools:
                juju_log("No thin pools found")
            elif len(thin_pools) == 1:
                juju_log("Thin pool {} found, extending with {}".format(
                    thin_pools[0],
                    new_device))
                extend_logical_volume_by_device(thin_pools[0], new_device)
            else:
                juju_log("Multiple thin pools ({}) found, "
                         "skipping auto extending with {}".format(
                             ','.join(thin_pools),
                             new_device))
    juju_log('LVM info after preparation')
    log_lvm_info()


def reduce_lvm_volume_group_missing(volume_group, extra_args=None):
    '''
    Remove all missing physical volumes from the volume group, if there
    are no logical volumes allocated on them.

    :param volume_group: str: Name of volume group to reduce.
    :param extra_args: list: List of extra args to pass to vgreduce
    '''
    if extra_args is None:
        extra_args = []

    command = ['vgreduce', '--removemissing'] + extra_args + [volume_group]
    subprocess.check_call(command)


def extend_lvm_volume_group(volume_group, block_device):
    '''
    Extend an LVM volume group onto a given block device.

    Assumes block device has already been initialized as an LVM PV.

    :param volume_group: str: Name of volume group to create.
    :block_device: str: Full path of PV-initialized block device.
    '''
    subprocess.check_call(['vgextend', volume_group, block_device])


def lvm_volume_group_exists(volume_group):
    """Check for the existence of a volume group.

    :param volume_group: str: Name of volume group.
    """
    try:
        subprocess.check_call(['vgdisplay', volume_group])
    except subprocess.CalledProcessError:
        return False
    else:
        return True


def remove_lvm_volume_group(volume_group):
    """Remove a volume group.

    :param volume_group: str: Name of volume group to remove.
    """
    subprocess.check_call(['vgremove', '--force', volume_group])


def ensure_lvm_volume_group_non_existent(volume_group):
    """Remove volume_group if it exists.

    :param volume_group: str: Name of volume group.
    """
    if not lvm_volume_group_exists(volume_group):
        return

    remove_lvm_volume_group(volume_group)


def log_lvm_info():
    """Log some useful information about how LVM is setup."""
    try:
        pvscan_output = subprocess.check_output(['pvscan']).decode('UTF-8')
        juju_log('pvscan:\n{}'.format(pvscan_output))
    except subprocess.CalledProcessError:
        juju_log('pvscan did not complete successfully; may not be setup yet')

    try:
        vgscan_output = subprocess.check_output(['vgscan']).decode('UTF-8')
        juju_log('vgscan:\n{}'.format(vgscan_output))
    except subprocess.CalledProcessError:
        juju_log('vgscan did not complete successfully')


def juju_log(msg):
    ch_hookenv.log(msg, ch_hookenv.INFO)


def prepare_volume(device):
    juju_log("prepare_volume: {}".format(device))
    clean_storage(device)
    create_lvm_physical_volume(device)
    juju_log("prepared volume: {}".format(device))


def has_partition_table(block_device):
    out = subprocess.check_output(['gdisk', '-l', block_device],
                                  stderr=subprocess.STDOUT).decode('UTF-8')
    return ("MBR: not present" not in out) or ("GPT: not present" not in out)


def clean_storage(block_device):
    '''Ensures a block device is clean.  That is:
        - unmounted
        - any lvm volume groups are deactivated
        - any lvm physical device signatures removed
        - partition table wiped

    :param block_device: str: Full path to block device to clean.
    '''
    for mp, d in mounts():
        if d == block_device:
            juju_log('clean_storage(): Found %s mounted @ %s, unmounting.' %
                     (d, mp))
            umount(mp, persist=True)

    if is_lvm_physical_volume(block_device):
        deactivate_lvm_volume_group(block_device)
        remove_lvm_physical_volume(block_device)

    zap_disk(block_device)


def filesystem_mounted(fs):
    return subprocess.call(['grep', '-wqs', fs, '/proc/mounts']) == 0


def _parse_block_device(block_device):
    ''' Parse a block device string and return either the full path
    to the block device, or the path to a loopback device and its size

    :param: block_device: str: Block device as provided in configuration

    :returns: (str, int): Full path to block device and 0 OR
                          Full path to loopback device and required size
    '''
    _none = ['None', 'none', None]
    if block_device in _none:
        return (None, 0)
    if block_device.startswith('/dev/'):
        return (block_device, 0)
    elif block_device.startswith('/'):
        _bd = block_device.split('|')
        if len(_bd) == 2:
            bdev, size = _bd
        else:
            bdev = block_device
            size = DEFAULT_LOOPBACK_SIZE
        return (bdev, bytes_from_string(str(size)))
    else:
        return ('/dev/{}'.format(block_device), 0)


class CinderLVMCharm(
        charms_openstack.charm.CinderStoragePluginCharm):

    name = 'cinder_lvm'
    release = 'queens'
    packages = []
    release_pkg = 'cinder-common'
    version_package = 'cinder-volume'
    stateless = True
    mandatory_config = ['alias', 'block-device']

    @property
    def service_name(self):
        # override backend name returned -- was hookenv.service_name()
        # unique backend names per host will not function well if
        # backend names are the same for all hosts, even if the
        # "volume_backend_name" is set to a unique value
        return get_backend_name()

    def cinder_configuration(self):
        configure_block_devices()

        driver_options = [
            ('volume_driver', VOLUME_DRIVER),
            ('volumes_dir', VOLUMES_DIR),
            ('volume_name_template', VOLUME_NAME_TEMPLATE),
            ('volume_group', get_volume_group_name()),
            ('volume_backend_name', get_backend_name()),
            ('lvm_type', ch_hookenv.config('allocation-type')),
            ('volume_clear', 'zero'),
            ('volume_clear_size', ch_hookenv.config('erase-size')),
        ]

        config_flags = ch_hookenv.config('config-flags')
        if config_flags:
            for flag in config_flags.split(','):
                tup = tuple(flag.split('=', 1))
                driver_options.append(tup)

        return driver_options
