lvm Storage Backend for Cinder
-------------------------------

Overview
========

This charm provides a lvm storage backend for use with the Cinder
charm.

To use:

    juju deploy cinder
    juju deploy cinder-lvm
    juju add-relation cinder-lvm cinder

Configuration
=============

See config.yaml for details of configuration options.
