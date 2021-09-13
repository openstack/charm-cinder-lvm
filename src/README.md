# Overview

The cinder-lvm charm provides an LVM backend for Cinder, the core OpenStack block storage (volume) service. It is a subordinate charm that is used in conjunction with the cinder charm.

> **Note**: The cinder-lvm charm is supported starting with OpenStack Queens.

# Usage

## Configuration

This section covers common and/or important configuration options. See file `config.yaml` for the full list of options, along with their descriptions and default values. See the [Juju documentation][juju-docs-config-apps] for details on configuring applications.

#### `allocation-type`

Refers to volume provisioning type. Values can be 'thin', 'thick', 'auto' (resolves to 'thin' if supported) , and 'default' (resolves to 'thick'). The default value is 'default'.

### `block-device`

Specifies a space-separated list of devices to use for LVM physical volumes. This is a mandatory option. Value types include:

* block devices (e.g. 'sdb' or '/dev/sdb')
* a path to a local file with the size appended after a pipe (e.g. '/path/to/file|10G'). The file will be created if necessary and be mapped to a loopback device. This is intended for development and testing purposes. The default size is 5G.

To prevent potential data loss an already formatted device (or one containing LVM metadata) cannot be used unless the `overwrite` configuration option is set to 'true'.

### `config-flags`

Comma-separated list of key=value config flags. These values will be added to standard options when injecting config into `cinder.conf`.

### `overwrite`

Permits ('true') the charm to attempt to overwrite storage devices (specified by the `block-devices` option) if they contain pre-existing filesystems or LVM metadata. The default is 'false'. A device in use on the host will never be overwritten.

## Deployment

To deploy, add a relation to the cinder charm:

  juju add-relation cinder-lvm:storage-backend cinder:storage-backend

# Documentation

The OpenStack Charms project maintains two documentation guides:

* [OpenStack Charm Guide][cg]: for project information, including development
  and support notes
* [OpenStack Charms Deployment Guide][cdg]: for charm usage information

# Bugs

Please report bugs on [Launchpad][lp-bugs-charm-cinder-lvm].

[cg]: https://docs.openstack.org/charm-guide
[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[lp-bugs-charm-cinder-lvm]: https://bugs.launchpad.net/charm-cinder-lvm/+filebug

