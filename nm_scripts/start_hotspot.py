"""
Start a local hotspot using NetworkManager.
You do this by sending a dict to AddConnection. 
The dict below was generated with n-m dump on an existing connection and then anonymised.

# manually (in base balena OS) add a local hotspot with NO password (open)
nmcli connection add type wifi ifname wlan0 con-name hotspot autoconnect yes ssid PFC_EDU mode ap
nmcli connection modify hotspot 802-11-wireless.mode ap ipv4.method shared 
nmcli connection up hotspot

# if you want a password on the hotspot, add this to the modify command:
# 802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.psk 'PASSWORD'


#
# Also check what the rust wifi-connect does
# cd /usr/src/app && ./wifi-connect -s hotspot

"""

from sdbus_block.networkmanager import (   
    NetworkManager,
    NetworkManagerSettings,
    NetworkManagerConnectionProperties,
    NetworkDeviceGeneric,
    DeviceState,
    DeviceType,
    DeviceCapabilities as Capabilities,
    ActiveConnection,
    ConnectivityState
)
import sdbus
import uuid
import os, sys, pprint
import logging
import functools
from utility import create_state_file

info = logging.getLogger().info

sdbus.set_default_bus(sdbus.sd_bus_open_system())
nm = NetworkManager()

connection_ID = 'dawnlite-hotspot'
properties: NetworkManagerConnectionProperties = {
 '802-11-wireless': {'band': ('s','bg'),
                     'mode': ('s','ap'),
                     'ssid': ('ay',b'DawnLite')},
 'connection': {'autoconnect': ('b',False),
                'id': ('s',connection_ID),
                'interface-name': ('s','wlan0'),
                'type': ('s','802-11-wireless'),
                'uuid': ('s',str(uuid.uuid4()))},
 'ipv4': {'address-data': ("aa{sv}",[{'address': ('s','192.168.42.1'), 'prefix': ('u',24)}]),
          'method': ('s','manual')},
 'ipv6': {'method': ('s','auto')}
}

# If we add many connections using the same id, things get messy. Check:
if NetworkManagerSettings().get_connections_by_id(connection_ID):
    info(f'Connections using ID "{connection_ID}" exist, remove them:')
    info(f'Run: nmcli connection delete "{connection_ID}"')
else:
    s = NetworkManagerSettings()
    connection_settings_dbus_path = s.add_connection(properties)
    created = "created and saved"

    info(f"New saved connection profile {created}, show it with:")
    info(f'nmcli connection show "{connection_ID}"|grep -v -e -- -e default')
    info("Settings used:")
    info(functools.partial(pprint.pformat, sort_dicts=False)(properties))

    # And connect
    # NetworkManager.NetworkManager.ActivateConnection(conn, dev, "/")
    conn = NetworkManagerSettings().get_connections_by_id(connection_ID)
    dev = 'wlan0'
    NetworkManager.activate_connection(conn, dev, "/")
    print(f"Activated connection={conn}, dev={dev}.")

    # create state file

    if create_state_file('hotspot'):
        print('Created Hotspot flag file')
    else:
        print('Could not create Hotspot flag file')

