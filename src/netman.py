# Start a local hotspot using NetworkManager.

# You must use https://developer.gnome.org/NetworkManager/1.2/spec.html
# to see the DBUS API that the python-NetworkManager module is communicating
# over (the module documentation is scant).

import sdbus
from sdbus_block.networkmanager import (
    NetworkManager,
    NetworkManagerSettings,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    DeviceType,
    AccessPoint,
    NetworkConnectionSettings
)

from sdbus_block.networkmanager.enums import (
    WpaSecurityFlags,
    AccessPointCapabilities,
    DeviceState
)

from sdbus_block.networkmanager.enums import DeviceType as DType

import uuid, os, sys, time, socket
from enum import Enum
from utility import get_connections
from utility import ( get_serial, string_or_numeric, create_state_file, get_config)
import logging


HOTSPOT_CONNECTION_NAME = 'dawnlite'
GENERIC_CONNECTION_NAME = 'python-wifi-connect'


CONFIG = get_config()
DEBUG = CONFIG['DEBUG'] == 'True'

sdbus.set_default_bus(sdbus.sd_bus_open_system())
nm = NetworkManager()
nm_settings = NetworkManagerSettings(sdbus.get_default_bus())

logger = logging.getLogger('wifi-connect')

def title(enum: Enum) -> str:
    """Get the name of an enum: 1st character is uppercase, rest lowercase"""
    return enum.name.title()

#------------------------------------------------------------------------------
# Returns True if we are connected to the internet, False otherwise.
def have_active_internet_connection(host: str="8.8.8.8", port: int=53, timeout: int=2):
   """
   Host: 8.8.8.8 (google-public-dns-a.google.com)
   OpenPort: 53/tcp
   Service: domain (DNS/TCP)
   """
   try:
     socket.setdefaulttimeout(timeout)
     socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
     return True
   except Exception as e:
     logger.error(f"Exception: {e}")
     return False


#------------------------------------------------------------------------------
# Remove ALL wifi connections - to start clean or before running the hotspot.
def delete_all_wifi_connections() -> None:
    """
    walk trhough all devices, then for each wifi device, find connections for it
    and delete them.
    """
    for device_path in NetworkManager().get_devices(): # loop over all devces
        generic_device = NetworkDeviceGeneric(device_path)
        device_ip4_conf_path: str = generic_device.ip4_config
        if device_ip4_conf_path == "/":
            continue # ignore devices with no profile
        if not generic_device.managed:
            continue # ignore unmanaged devices
        dev_type = DeviceType(generic_device.device_type).name
        dev_name = generic_device.interface

        if dev_type == DeviceType.WIFI.name:
            if connections_dict := get_connections(dev_name, dev_type):
                for (timestamp,(connection_id, uuid)) in connections_dict.items():
                    nm_settings.delete_connection_by_uuid(uuid)

    time.sleep(2)


#------------------------------------------------------------------------------
# Stop and delete the hotspot.
# Returns True for success or False (for hotspot not found or error).
def stop_hotspot()->None:
    return stop_connection(HOTSPOT_CONNECTION_NAME)


#------------------------------------------------------------------------------
# Generic connection stopper / deleter.
def stop_connection(conn_name:str =GENERIC_CONNECTION_NAME)->bool:
    # Find the hotspot connection
    result = False
    for device_path in NetworkManager().get_devices(): # loop over all devces
        generic_device = NetworkDeviceGeneric(device_path)
        device_ip4_conf_path: str = generic_device.ip4_config
        if device_ip4_conf_path == "/":
            continue # ignore devices with no profile
        if not generic_device.managed:
            continue # ignore unmanaged devices
        dev_type = DeviceType(generic_device.device_type).name
        dev_name = generic_device.interface

        if dev_type == DeviceType.WIFI.name:
            if connections := get_connections(dev_name, dev_type):
                for connection in connections.items():
                    (timestamp,(connection_id, uuid)) = connection
                    if connection_id == conn_name: 
                        nm_settings.delete_connection_by_uuid(uuid)
                        result = True
    time.sleep(2)
    return result


#------------------------------------------------------------------------------
# Return a list of available SSIDs and their security type, 
# or [] for none available or error.
def get_list_of_access_points():
    # bit flags we use when decoding what we get back from NetMan for each AP
    NM_SECURITY_NONE       = 0x0
    NM_SECURITY_WEP        = 0x1
    NM_SECURITY_WPA        = 0x2
    NM_SECURITY_WPA2       = 0x4
    NM_SECURITY_ENTERPRISE = 0x8

    ssids = [] # list we return

    for device_path in NetworkManager().get_devices(): # loop over all devces
        generic_device = NetworkDeviceGeneric(device_path)
        device_ip4_conf_path: str = generic_device.ip4_config
        if device_ip4_conf_path == "/":
            continue # ignore devices with no profile
        if not generic_device.managed:
            continue # ignore unmanaged devices
        dev_type = DeviceType(generic_device.device_type).name
        if dev_type != DeviceType.WIFI.name:
            continue
        wifi_device = NetworkDeviceWireless(device_path)
        wifi_device.request_scan(options={}) # update the available ssids for this device
        for access_point_path in wifi_device.access_points:
            ap = AccessPoint(access_point_path)

            #don't addd blank ssids
            if ap.ssid == b'':
                continue


            # Get Flags, WpaFlags and RsnFlags, all are bit OR'd combinations 
            # of the NM_802_11_AP_SEC_* bit flags.  
            # in this version, uses the enums in WpaSecurityFlags/
            # https://developer.gnome.org/NetworkManager/1.2/nm-dbus-types.html#NM80211ApSecurityFlags

            security = WpaSecurityFlags.NONE

            # Based on a subset of the flag settings we can determine which
            # type of security this AP uses.  
            # We can also determine what input we need from the user to connect to
            # any given AP (required for our dynamic UI form).
            
            if ap.flags & AccessPointCapabilities.PRIVACY and \
                    ap.wpa_flags == WpaSecurityFlags.NONE and \
                    ap.rsn_flags == WpaSecurityFlags.NONE:
                security = NM_SECURITY_WEP

            if ap.wpa_flags != AccessPointCapabilities.NONE:
                security = NM_SECURITY_WPA

            if ap.rsn_flags != AccessPointCapabilities.NONE:
                security = NM_SECURITY_WPA2

            if ap.wpa_flags & WpaSecurityFlags.AUTH_802_1X or \
                    ap.rsn_flags & WpaSecurityFlags.AUTH_802_1X:
                security = NM_SECURITY_ENTERPRISE

            logger.debug(f'{ap.ssid.decode():15} Flags=0x{ap.flags:X} WpaFlags=0x{ap.wpa_flags:X} RsnFlags=0x{ap.rsn_flags:X}')

            # Decode our flag into a display string
            security_str = ''
            if security == NM_SECURITY_NONE:
                security_str = 'NONE'
    
            if security & NM_SECURITY_WEP:
                security_str = 'WEP'
    
            if security & NM_SECURITY_WPA:
                security_str = 'WPA'
    
            if security & NM_SECURITY_WPA2:
                security_str = 'WPA2'
    
            if security & NM_SECURITY_ENTERPRISE:
                security_str = 'ENTERPRISE'

            entry = {"ssid": ap.ssid, "security": security_str}

     
            # Don't add duplicates to the list, issue #8
            if ssids.__contains__(entry):
                continue

            ssids.append(entry)

    logger.debug(f'Available SSIDs: {ssids}')
    return ssids


#------------------------------------------------------------------------------
# Get hotspot SSID name.
def get_hotspot_SSID():
    serial = get_serial()
    return CONFIG['HOTSPOT_BASE'] + get_serial()[-4:]


#------------------------------------------------------------------------------
# Start a local hotspot on the wifi interface.
# Returns True for success, False for error.
def start_hotspot():
    return connect_to_AP(CONN_TYPE_HOTSPOT, HOTSPOT_CONNECTION_NAME, \
            get_hotspot_SSID())


#------------------------------------------------------------------------------
# Supported connection types for the function below.
CONN_TYPE_HOTSPOT        = 'hotspot'
CONN_TYPE_SEC_NONE       = 'NONE' # MIT
CONN_TYPE_SEC_PASSWORD   = 'PASSWORD' # WPA, WPA2 and WEP
CONN_TYPE_SEC_ENTERPRISE = 'ENTERPRISE' # MIT SECURE


#------------------------------------------------------------------------------
# Generic connect to the user selected AP function.
# Returns True for success, or False.
def connect_to_AP(conn_type=None, conn_name=GENERIC_CONNECTION_NAME, \
        ssid=None, username=None, password=None):

    logger.debug(f"connect_to_AP conn_type={conn_type} conn_name={conn_name} ssid={ssid} username={username} password={password}")

    if conn_type is None or ssid is None:
        logger.error(f'connect_to_AP() Error: Missing args conn_type or ssid')
        return False

    bSSID = ssid.encode('utf-8')
    try:
        # This is the hotspot that we turn on, on the RPI so we can show our
        # captured portal to let the user select an AP and provide credentials.
        hotspot_dict = {
            '802-11-wireless': {'band': ('s','bg'),
                                'mode': ('s','ap'),
                                'ssid': ('ay', bSSID)},
            'connection': {'autoconnect': ('b', False),
                           'id': ('s', conn_name),
                        #    'interface-name': ('s','wlan0'),  # could make this a parameter
                           'type': ('s','802-11-wireless'),
                           'uuid': ('s', str(uuid.uuid4()))},
            'ipv4': {'address-data': ('aa{sv}',
                        [{'address': ('s','192.168.42.1'), 'prefix': ('u',24)}]),
                     'method': ('s','manual')},
            'ipv6': {'method': ('s','auto')}
        }

# debugrob: is this realy a generic ENTERPRISE config, need another?
# debugrob: how do we handle connecting to a captured portal?

        # This is what we use for "MIT SECURE" network.
        enterprise_dict = {
            '802-11-wireless': {'mode': ('s','infrastructure'),
                                'security': ('s','802-11-wireless-security'),
                                'ssid': ('ay',bSSID)},
            '802-11-wireless-security': 
                {'auth-alg': ('s','open'), 'key-mgmt': ('s','wpa-eap')},
            '802-1x': {'eap': ('as', ['peap']),
                       'identity':('s', username if username != None else ""),
                       'password': ('s', password if password != None else ""),
                       'phase2-auth': ('s','mschapv2')},
            'connection': {'id': ('s',conn_name),
                           'type': ('s', '802-11-wireless'),
                        #    'interface-name': ('s','wlan0'),
                           'uuid': ('s', str(uuid.uuid4()))},
            'ipv4': {'method': ('s','auto')},
            'ipv6': {'method': ('s','auto')}
        }

        # No auth, 'open' connection.
        none_dict = {
            '802-11-wireless': {'mode': ('s','infrastructure'),
                                'ssid': ('ay', bSSID)},
            'connection': {'id': ('s',conn_name),
                           'type': ('s','802-11-wireless'),
                        #    'interface-name': ('s','wlan0'),
                           'uuid': ('s',str(uuid.uuid4()))},
            'ipv4': {'method': ('s','auto')},
            'ipv6': {'method': ('s','auto')}
        }

        # Hidden, WEP, WPA, WPA2, password required.
        passwd_dict = {
            '802-11-wireless': {'mode': ('s','infrastructure'),
                                'security': ('s','802-11-wireless-security'),
                                'ssid': ('ay', bSSID)},
            '802-11-wireless-security': 
                {'key-mgmt': ('s','wpa-psk'), 'psk': ('s', password if password != None else '')},
            'connection': {'id': ('s', conn_name),
                        'type': ('s','802-11-wireless'),
                        # 'interface-name': ('s','wlan0'),
                        'uuid': ('s', str(uuid.uuid4())),
                        },
            'ipv4': {'method': ('s', 'auto')},
            'ipv6': {'method': ('s', 'auto')}
        }

        conn_dict = None
        conn_str = ''
        if conn_type == CONN_TYPE_HOTSPOT:
            conn_dict = hotspot_dict
            conn_str = 'HOTSPOT'

        if conn_type == CONN_TYPE_SEC_NONE:
            conn_dict = none_dict 
            conn_str = 'OPEN'

        if conn_type == CONN_TYPE_SEC_PASSWORD:
            conn_dict = passwd_dict 
            conn_str = 'WEP/WPA/WPA2'

        if conn_type == CONN_TYPE_SEC_ENTERPRISE:
            conn_dict = enterprise_dict 
            conn_str = 'ENTERPRISE'

        if conn_dict is None:
            print(f'connect_to_AP() Error: Invalid conn_type="{conn_type}"')
            return False

        #print(f"new connection {conn_dict} type={conn_str}")

        if nm_settings.get_connections_by_id(conn_name):
            delete_all_wifi_connections()
            # logger.warning(f'Connection "{conn_name}" exists, remove it first')
            # logger.warning(f'Run: nmcli connection delete "{conn_name}"')
            # return ""
        
        nm_settings.add_connection(conn_dict)
        logger.info(f"Added connection {conn_name} of type {conn_str}")

        # Now find this connection and its device
        connections_paths = nm_settings.connections # returns the paths to the connections
        connections = {}
        paths = {}
        for path in connections_paths:
            connection_service = NetworkConnectionSettings(path)
            profile = connection_service.get_profile()
            connection = profile.connection
            connections[connection.connection_id] = profile
            paths[connection.connection_id] = path
        conn = connections[conn_name]
        conn_path = paths[conn_name]

        # Find a suitable device
        conn_connection = conn.connection
        ctype = conn_connection.connection_type
        device_paths = nm.get_devices()
        for device_path in device_paths:
            generic = NetworkDeviceGeneric(device_path)
            dev = generic.interface
            dtype = generic.device_type
            if ctype =='802-11-wireless' and  dtype == DType.WIFI:
                active_connection = generic.active_connection
                break
        else:
            logger.error(f"connect_to_AP() Error: No suitable and available {ctype} device found.")
            return False

        # check to see if wlan0 is active and if so, deactivate the connection.

        # And connect
        if active_connection and active_connection != '/':
            nm.deactivate_connection(active_connection)
        dev_object = nm.get_device_by_ip_iface(dev)
        nm.activate_connection(conn_path, dev_object, "/")
        logger.info(f"Activated connection={conn_name}.")

        # Wait for ADDRCONF(NETDEV_CHANGE): wlan0: link becomes ready
        logger.info(f'Waiting for connection to become active...')
        loop_count = 0

         
        while NetworkDeviceWireless(dev_object).state != DeviceState.ACTIVATED:
            logger.debug(f'dev.state={NetworkDeviceWireless(dev_object).state}')
            time.sleep(1)
            loop_count += 1
            if loop_count > 30: # only wait 30 seconds max
                break

        if NetworkDeviceWireless(dev_object).state == DeviceState.ACTIVATED:
            logger.info(f'Connection {conn_name} is live.')

            file_type = 'hotspot' if conn_str == 'HOTSPOT' else 'client'
            if create_state_file(file_type):
                logger.info(f'{file_type} flag file create')
            else:
                logger.error(f'Could not create {file_type} flag file')

            return True

    except Exception as e:
        logger.error(f'Connection error {e}')

    logger.error(f'Connection {conn_name} failed.')
    return False

if __name__ == "__main__":
    start_hotspot()




