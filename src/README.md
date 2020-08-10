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

It will prepare the devices (format) and then will talk to main cinder
charm to pass on configuration which cinde charm will inject into it's
own configuration file. After that, it does nothing except watch for
config changes and reconfig cinder.

The configuration is passed over to cinder using a juju relation.
Although cinder has a few different services, it is the cinder-volume
service that will make use of the configuration added.

Note: The devices must be local to the cinder-volume, so you will
probably want to deploy this service on the compute hosts, since the
cinder-volume that will be running on the controller nodes will not
have access to any physical device (it is normally deployed in lxd).

A more complete example, using a bundle would be the folowing.

Your normal cinder deployed to controllers, will all services running:

    hacluster-cinder:
      charm: cs:hacluster
    cinder:
      charm: cs:cinder
      num_units: 3
      constraints: *combi-access-constr
      bindings:
        "": *oam-space
        public: *public-space
        admin: *admin-space
        internal: *internal-space
        shared-db: *internal-space
      options:
        worker-multiplier: *worker-multiplier
        openstack-origin: *openstack-origin
        block-device: None
        glance-api-version: 2
        vip: *cinder-vip
        use-internal-endpoints: True
        region: *openstack-region
      to:
      - lxd:1003
      - lxd:1004
      - lxd:1005

Extra cinder-volume only services running on compute-nodes (basically the same as above but with "enabled-services: volume"). Take care to leave "block-device: None" because we do not want to use internal lvm functionality from the cinder charm, and will instead make the cinder-lvm charm do that:

    cinder-volume:
      charm: cs:cinder
      num_units: 9
      constraints: *combi-access-constr
      bindings:
        "": *oam-space
        public: *public-space
        admin: *admin-space
        internal: *internal-space
        shared-db: *internal-space
      options:
        worker-multiplier: *worker-multiplier
        openstack-origin: *openstack-origin
        enabled-services: volume
        block-device: None
        glance-api-version: 2
        use-internal-endpoints: True
        region: *openstack-region
      to:
      - 1000
      - 1001
      - 1002
      - 1003
      - 1004
      - 1005
      - 1006
      - 1007
      - 1008

And then the cinder-lvm charm (as a subordinate charm):

    cinder-lvm-fast:
      charm: cs:cinder-lvm
      num_units: 0
      options:
        alias: fast
        block-device: /dev/nvme0n1
        allocation-type: default
        erase-size: '50'
        unique-backend: true
    cinder-lvm-slow:
      charm: cs:cinder-lvm
      num_units: 0
      options:
        alias: slow
        block-device: /dev/sdb /dev/sdc /dev/sdd
        allocation-type: default
        erase-size: '50'
        unique-backend: true

And then the extra relations for cinder-volume and cinder-lvm-[foo]:

    - [ cinder-volume, mysql ]
    - [ "cinder-volume:amqp", "rabbitmq-server:amqp" ]
    - [ "cinder-lvm-fast", "cinder-volume" ]
    - [ "cinder-lvm-slow", "cinder-volume" ]


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
in use (formatted as physical volumes or other filesystems), unless they
already have the desired volume group (in which case it will be used
instead of creating a new one).

This charm only prepares devices for lvm and configures cinder and do
not execute any active function, therefore there is not need for
high-availability.

