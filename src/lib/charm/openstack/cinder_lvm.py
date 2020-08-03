import charms_openstack.charm
import charmhelpers.core.hookenv as ch_hookenv  # noqa

charms_openstack.charm.use_defaults('charm.default-select-release')


class CinderlvmCharm(
        charms_openstack.charm.CinderStoragePluginCharm):

    name = 'cinder_lvm'
    version_package = 'cinder-volume'
    release = 'ocata'
    packages = [version_package]
    stateless = True
    # Specify any config that the user *must* set.
    mandatory_config = []

    def cinder_configuration(self):
        volume_driver = ''
        driver_options = [
            ('volume_driver', volume_driver),
            # Add config options that needs setting on cinder.conf
        ]
        return driver_options


class CinderlvmCharmRocky(CinderlvmCharm):

    # Rocky needs py3 packages.
    release = 'rocky'
    version_package = 'cinder-volume'
    packages = [version_package]
