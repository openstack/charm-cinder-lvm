lvm Storage Backend for Cinder
-------------------------------

Overview
========

This charm provides a lvm storage backend for use with the Cinder
charm. It is intended to be used as a subordinate to main cinder charm.

To use:

    juju deploy cinder
    juju deploy cinder-lvm
    juju add-relation cinder-lvm cinder


Configuration
=============

See config.yaml for details of configuration options.

One or more block devices (local to the charm unit) are used as an LVM
physical volumes, on which a volume group is created. A logical volume
is created ('openstack volume create') and exported to a cloud instance
via iSCSI ('openstack server add volume').

**Note**: It is not recommended to use the LVM storage method for
anything other than testing or for small non-production deployments.

**Important** Make sure the designated block devices exist and are not
in use (formatted as physical volumes or other filesystems).

This charm only configures cinder and do not execute any active
function, therefore there is not need for high-availability.
