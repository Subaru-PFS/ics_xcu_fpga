#!/bin/bash

# Print the RTD Spartan-6 FPGA's bus address, fetched from sysfs. This ID is suitable for various other purposes:
#
# List the device's PCI properties:
#     lspci -vvv -s $(get_fpga_bus_id.sh)
# 
# Get a mmap-able window. The BEE machine's /etc/udev/rules.d/10-pfs.rules makes that file accessible by the pfs group.
#     mmap_file=/sys/bus/pci/devices/$(get_fpga_bus_id.sh)/resource0
#
#

BUS_ID=$(lspci -D -d 1435:5800 | sed 's/ .*//')
echo $BUS_ID

# Success?
test "$BUS_ID"
