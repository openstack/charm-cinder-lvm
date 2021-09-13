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

import charmhelpers
import charm.openstack.cinder_lvm as cinder_lvm
import charms_openstack.test_utils as test_utils


class MockDevice:
    def __init__(self, path, **kwargs):
        self.path = path
        kwargs.setdefault('size', 0)
        self.attrs = kwargs

    @property
    def size(self):
        return self.attrs['size']

    def is_block(self):
        return self.attrs.get('block', False)

    def is_loop(self):
        return self.attrs.get('loop', False)

    def has_partition_table(self):
        return self.attrs.get('partition-table')


class MockLVM:
    def __init__(self):
        self.vgroups = {}
        self.devices = []
        self.mount_points = {}   # Maps device paths to device objects.

    def reduce(self, group):
        self.vgroups.pop(group, None)

    def extend(self, group, device=None):
        dev_group = self.vgroups.setdefault(group, set())
        if device:
            dev_group.add(device)

    def exists(self, group):
        return group in self.vgroups

    def remove(self, group):
        self.vgroups.pop(group)

    def ensure_non_existent(self, group):
        self.vgroups.pop(group, None)

    def list_vgroup(self, device):
        for group, dev in self.vgroups.items():
            if dev == device:
                return group
        return ''

    def fs_mounted(self, fs):
        return fs in self.mount_points

    def mounts(self):
        return list((v.path, k) for k, v in self.mount_points.items())

    def umount(self, fs):
        for k, v in self.mount_points.items():
            if fs == v.path:
                del self.mount_points[k]
                return

    def find_device(self, path):
        for dev in self.devices:
            if dev.path == path:
                return dev

    def add_device(self, device, **kwargs):
        dev = MockDevice(device, **kwargs)
        self.devices.append(dev)
        return dev

    def is_block_device(self, path):
        dev = self.find_device(path)
        return dev is not None and dev.is_block()

    def ensure_loopback_dev(self, path, size):
        dev = self.find_device(path)
        if dev is not None:
            dev.attrs['size'] = size
            dev.attrs['loop'] = True
        else:
            self.devices.append(MockDevice(path, loop=True, size=size))
        return dev.path

    def is_device_mounted(self, path):
        return any(x.path == path for x in self.mount_points.values())

    def mount_path(self, path, device, **kwargs):
        dev = self.find_device(device)
        if dev is not None:
            self.attrs.update(kwargs)
        else:
            self.mount_points[path] = self.add_device(device, **kwargs)

    def has_partition_table(self, device):
        dev = self.find_device(device)
        return dev is not None and dev.has_partition_table()

    def reset(self):
        self.vgroups.clear()
        self.devices.clear()
        self.mount_points.clear()


class TestCinderLVMCharm(test_utils.PatchHelper):

    @classmethod
    def setUpClass(cls):
        cls.DEFAULT_CONFIG = {'overwrite': False,
                              'remove-missing': False, 'alias': 'test-alias',
                              'remove-missing-force': False}
        cls.LVM = MockLVM()

    def setUp(self):
        super().setUp()
        self._config = self.DEFAULT_CONFIG.copy()
        lvm = self.LVM

        def cf(key=None):
            if key is None:
                return self._config
            return self._config.get(key)

        self.patch_object(charmhelpers.core.hookenv, 'config')
        self.patch_object(cinder_lvm, 'mounts')
        self.patch_object(cinder_lvm, 'umount')
        self.patch_object(cinder_lvm, 'is_block_device')
        self.patch_object(cinder_lvm, 'zap_disk')
        self.patch_object(cinder_lvm, 'is_device_mounted')
        self.patch_object(cinder_lvm, 'ensure_loopback_device')
        self.patch_object(cinder_lvm, 'create_lvm_physical_volume')
        self.patch_object(cinder_lvm, 'create_lvm_volume_group')
        self.patch_object(cinder_lvm, 'deactivate_lvm_volume_group')
        self.patch_object(cinder_lvm, 'is_lvm_physical_volume')
        self.patch_object(cinder_lvm, 'list_lvm_volume_group')
        self.patch_object(cinder_lvm, 'list_thin_logical_volume_pools')
        self.patch_object(cinder_lvm, 'filesystem_mounted')
        self.patch_object(cinder_lvm, 'lvm_volume_group_exists')
        self.patch_object(cinder_lvm, 'remove_lvm_volume_group')
        self.patch_object(cinder_lvm, 'ensure_lvm_volume_group_non_existent')
        self.patch_object(cinder_lvm, 'log_lvm_info')
        self.patch_object(cinder_lvm, 'has_partition_table')
        self.patch_object(cinder_lvm, 'reduce_lvm_volume_group_missing')
        self.patch_object(cinder_lvm, 'extend_lvm_volume_group')

        self.config.side_effect = cf
        cinder_lvm.mounts.side_effect = lvm.mounts
        cinder_lvm.umount.side_effect = lvm.umount
        cinder_lvm.is_block_device.side_effect = lvm.is_block_device
        cinder_lvm.is_device_mounted.side_effect = lvm.is_device_mounted
        cinder_lvm.ensure_loopback_device.side_effect = lvm.ensure_loopback_dev
        cinder_lvm.create_lvm_volume_group.side_effect = lvm.extend
        cinder_lvm.is_lvm_physical_volume.return_value = False
        cinder_lvm.list_lvm_volume_group.side_effect = lvm.list_vgroup
        cinder_lvm.list_thin_logical_volume_pools.return_value = []
        cinder_lvm.filesystem_mounted.side_effect = lvm.fs_mounted
        cinder_lvm.lvm_volume_group_exists.side_effect = lvm.exists
        cinder_lvm.remove_lvm_volume_group.side_effect = lvm.remove
        cinder_lvm.ensure_lvm_volume_group_non_existent.side_effect = \
            lvm.ensure_non_existent
        cinder_lvm.has_partition_table.side_effect = lvm.has_partition_table
        cinder_lvm.extend_lvm_volume_group.side_effect = lvm.extend
        self._config['block-device'] = '/dev/sdb'

    def tearDown(self):
        super().tearDown()
        self.LVM.reset()

    def _patch_config_and_charm(self, config):
        self._config.update(config)
        return cinder_lvm.CinderLVMCharm()

    def test_cinder_base(self):
        charm = self._patch_config_and_charm({})
        self.assertEqual(charm.name, 'cinder_lvm')
        self.assertEqual(charm.version_package, 'cinder-volume')
        self.assertEqual(charm.packages, [])

    def test_cinder_configuration(self):
        charm = self._patch_config_and_charm(
            {'a': 'b', 'config-flags': 'val=3'})
        config = charm.cinder_configuration()
        self.assertEqual(config[-1][1], '3')
        self.assertNotIn('a', list(x[0] for x in config))

    def test_cinder_lvm_ephemeral_mount(self):
        ephemeral_path, ephemeral_dev = 'somepath', '/dev/sdc'
        charm = self._patch_config_and_charm(
            {'ephemeral-unmount': ephemeral_path})
        self.LVM.mount_path(ephemeral_path, ephemeral_dev)
        charm.cinder_configuration()
        cinder_lvm.filesystem_mounted.assert_called()
        cinder_lvm.umount.assert_called()
        self.assertFalse(cinder_lvm.is_device_mounted(ephemeral_path))

    def test_cinder_lvm_block_dev_none(self):
        charm = self._patch_config_and_charm({'block-device': 'none'})
        charm.cinder_configuration()
        self.assertFalse(self.LVM.mount_points)

    def test_cinder_lvm_single_vg(self):
        self.LVM.add_device(self._config['block-device'], block=True)
        charm = self._patch_config_and_charm({})
        charm.cinder_configuration()
        cinder_lvm.is_device_mounted.assert_called()
        cinder_lvm.zap_disk.assert_called()
        self.assertTrue(self.LVM.exists(cinder_lvm.get_volume_group_name()))

    def test_cinder_lvm_loopback_dev(self):
        loop_dev = '/sys/loop0'
        self.LVM.add_device(loop_dev, loop=True)
        charm = self._patch_config_and_charm(
            {'block-device': loop_dev + '|100'})
        charm.cinder_configuration()
        dev = self.LVM.find_device(loop_dev)
        self.assertTrue(dev)
        self.assertEqual(dev.size, '100')
