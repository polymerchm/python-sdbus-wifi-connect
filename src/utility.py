
#
# Utility functions borrowed  from 
# python-sdbus-networkmanager examples
#


import sdbus
from sdbus_block.networkmanager import (
    ConnectionType,
    NetworkConnectionSettings,
    NetworkManagerSettings,
    NetworkManager,  
    NetworkDeviceGeneric,
    DeviceType,
)

import os
from enum import Enum
import logging
from dotenv import dotenv_values

logger = logging.getLogger('wifi-connect')




# from typing import Any, Dict, List, Optional, Tuple
# NetworkManagerAddressData = List[Dict[str, Tuple[str, Any]]]


def get_connections(ifname: str, dev_type: str) -> dict[int,tuple[str, str]] | None:
    """
    Return all connections used by for this device/interface

    It uses getattr(ConnectionType, dev_type) to get the connection_type
    used for connection_profiles for this DeviceType.

    return a dictionary with key of timestamp and value of (name, UUID and its delete function) as a tuple

    """
    settings_service = NetworkManagerSettings()
    connection_paths: list[str] = settings_service.connections
    conns = {}
    for connection_path in connection_paths:
        connection_manager = NetworkConnectionSettings(connection_path)
        connection = connection_manager.get_profile().connection
        # Filter connection profiles matching the connection type for the device:
        if connection.connection_type != getattr(ConnectionType, dev_type):
            continue
        # If the interface_name of a connection profiles is set, it must match:
        if connection.interface_name and connection.interface_name != ifname:
            continue
        # If connection.timestamp is not set, it was never active. Set it to 0:
        if not connection.timestamp:
            connection.timestamp = 0
        if not connection.uuid:
            connection.uuid = ""
       
        # Record the connection_ids of the matches, and timestamp is the key:
        conns[connection.timestamp] = (connection.connection_id, connection.uuid,)
    if not len(conns):
        return None
    # Returns the connections
    return conns

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
            generic_dev.delete()
            logger.info(f"deleted {dev}")


def get_serial()->str:
  # Extract serial from cpuinfo file
  cpuserial = "0000000000000000"
  try:
    with open('/proc/cpuinfo','r') as f:
        for line in f:
            if line[0:6]=='Serial':
                cpuserial = line[10:26]
                break
  except:
    cpuserial = "ERROR000000000"
 
  return cpuserial
        
def string_or_numeric(value: any)->int | float | str:
    try:
        int_value = int(value)
        return int_value
    except:
        try:
            float_value = float(value)
            return float_value
        except:
            return value
        

def create_state_file(value: str)->bool:
    base = '/etc/wifi_state'
    files = {'hotspot':os.path.join(base,'hotspot'), 'client':os.path.join(base,'client')}
    if not value in files:
       return False
    if not os.path.exists(base):
        try:
           os.mkdir(base)
        except:
            return False
    if value == 'client':
        file_to_remove = files['hotspot']
        file_to_create = files['client']
    else:
        file_to_remove = files['client']
        file_to_create = files['hotspot']
    try:
        if os.path.exists(file_to_remove):
            os.remove(file_to_remove)
        if not os.path.exists(file_to_create):
            with open(file_to_create,'a') as f:
                os.utime(file_to_create,None)
        else:
            return False # should not exist
    except:
        return False # system error
    return True

def get_config():
    config = {}

    env = dotenv_values('.env.global', verbose=True)
    for (key,val) in env.items():
        config[key] = string_or_numeric(val)
    return config

    if __name__ == '__main__':
        print(create_state_file('client'))