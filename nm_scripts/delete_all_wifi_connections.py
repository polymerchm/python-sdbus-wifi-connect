#
# use python-sdbus-networkmanager library

import sdbus
from sdbus_block.networkmanager import (
    NetworkManager,  
    NetworkDeviceGeneric,
    DeviceType,
)

from enum import Enum



def title(enum: Enum) -> str:
    """Get the name of an enum: 1st character is uppercase, rest lowercase"""
    return enum.name.title()


### Run this before we run 'wifi-connect' to clear out pre-configured networks
def clear_connections():
    # Get all known connections
    # connections = NetworkManager.Settings.ListConnections()
    
    nm = NetworkManager()
    # Delete the '802-11-wireless' connections

    device_paths =  nm.devices

    for device_path in device_paths:
        generic_dev = NetworkDeviceGeneric(device_path)

        dev = generic_dev.interface
        type = title(DeviceType(generic_dev.device_type))
        if "Wifi" in type:
            # generic_dev.delete()
            print(f"deleted {dev}")


if __name__=="__main__":
    sdbus.set_default_bus(sdbus.sd_bus_open_system()) # set the defult bus to the system bus
    clear_connections()

