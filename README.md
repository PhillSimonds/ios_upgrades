IOS Upgrade
=======

This set of scripts is used to upgrade code on IOS devices in a programmatic way. 


# How it works

These scripts utilize the nornir library to execute IOS upgrade tasks against an inventory of networking devices. Nornsible is used to provide ansible-like host/group limits and tagging functionality so that the script can be limited to only those hosts/groups against which it should executed at time of execution. There are a few components which need to be specified in order for the scripts to work correctly.

- Inside of the nornir inventory, a 'primary_image' key should be specified with a value corresponding to the name of the image which the target device should be running.
- The "NORNIR_CONFIG_FILE" environment variable is used to set the config file. The full path of this file needs be specified. e.g. '/home/cool_user/nornir/inventory/config.yaml'
- The "IOS_IMAGES_DIR" environment variable is used to set the location on the local system where ios images can be found

Right now, two scripts exist - one to prepare devices for upgrade, and another to reboot the devices. Verification of the version upgrade on devices is not currently accounted for in this set of scripts.

# Scripts Included


## prepare_devices.py

This script does the following:
- Look for images currently in the target device's flash filesystem, and remove any files which don't correspond to either the running image, or to the target image
- Copies the primary image over to the device and verify's it's MD5 hash
- Sets boot vars on the target device. If the device is already on the target version of code, only a boot variable for the target image is set. If the device is not yet on the target version of code, two boot variables are set, the first for the target image, the second for the current image. This is done to ensure the device will boot into it's current image if booting into the new image fails
- Verifies that the target and backup (if applicable) images both exist in flash, that the boot vars are set correctly, and the config is written
- Prints a simple colored output indicating the readiness of the target device to be rebooted in the following color scheme:
  - red: Indicates an issue which will cause the device to fail an upgrade
  - green: Indicates that everything is as expected
  - yellow: Indicates a warning condition, which will not impede the upgrade, but should be accounted for

## reboot_devices.py

This script saves configs on target devices, reboots them, and ping's them until they're back up. Once back up, a message is output to the terminal indicating how long the device was down. If the device does not respond to ICMP within 20 minutes, a message is output to the terminal indicating that the device is not responding to ICMP


# Supported Platforms

Currently, ISRG2s are the only supported platform. Work is being done to support the 2960 platform next, and will be followed by work to upgrade other platforms.