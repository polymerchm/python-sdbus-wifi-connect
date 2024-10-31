# Display all visible SSIDs
# When connected to an AP, that is all that will be in the list.
# When there is no active connection, this will show all visible APs.
# 
# updated to use python-sdbus-networkmanager
#
# NOTE: To see all available access points, this script must be run as root (using sudo)

from sdbus_block.networkmanager import (   
    NetworkManager,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    AccessPoint
)

from sdbus_block.networkmanager.enums import (    
    WpaSecurityFlags,
    AccessPointCapabilities,
    DeviceType)
import sdbus

NM_SECURITY_NONE       = 0x0
NM_SECURITY_WEP        = 0x1
NM_SECURITY_WPA        = 0x2
NM_SECURITY_WPA2       = 0x4
NM_SECURITY_ENTERPRISE = 0x8

USER_INPUT_NONE     = 0x0
USER_INPUT_PASSWORD = 0x1
USER_INPUT_USERNAME = 0x2

sdbus.set_default_bus(sdbus.sd_bus_open_system())
nm = NetworkManager()


for device_path in nm.get_devices():
    device = NetworkDeviceGeneric(device_path)
    if device.device_type != DeviceType.WIFI:
        continue
    wifi_device = NetworkDeviceWireless(device_path)
    wifi_device.request_scan(options={}) # update the available ssids for this device
    for access_point_path in wifi_device.access_points:
        ap = AccessPoint(access_point_path)
        #print('%-30s %dMHz %d%%' % (ap.Ssid, ap.Frequency, ap.Strength))

        # Get Flags, WpaFlags and RsnFlags, all are bit OR'd combinations 
        # of the NM_802_11_AP_SEC_* bit flags.
        # https://developer.gnome.org/NetworkManager/1.2/nm-dbus-types.html#NM80211ApSecurityFlags

        security = NM_SECURITY_NONE
        user_input = USER_INPUT_NONE

        # Based on a subset of the flag settings we can determine which
        # type of security this AP uses.  
        # We can also determine what input we need from the user to connect to
        # any given AP (required for our dynamic UI form).
        if ap.flags & AccessPointCapabilities.NONE and \
                ap.wpa_flags == WpaSecurityFlags.NONE and \
                ap.rsn_flags == WpaSecurityFlags.NONE:
            security = NM_SECURITY_WEP
            user_input = USER_INPUT_PASSWORD

        if ap.wpa_flags != WpaSecurityFlags.NONE:
            security = NM_SECURITY_WPA
            user_input = USER_INPUT_PASSWORD

        if ap.rsn_flags != WpaSecurityFlags.NONE:
            security = NM_SECURITY_WPA2
            user_input = USER_INPUT_PASSWORD

        if ap.wpa_flags & WpaSecurityFlags.AUTH_802_1X or \
                ap.rsn_flags &WpaSecurityFlags.AUTH_802_1X:
            security = NM_SECURITY_ENTERPRISE
            user_input = USER_INPUT_PASSWORD
            user_input |= USER_INPUT_USERNAME

        # Decode our flag into a display string
        security_str = ''
        if security == NM_SECURITY_NONE:
            security_str = 'NONE'

        if security & NM_SECURITY_WEP:
            security_str += 'WEP '

        if security & NM_SECURITY_WPA:
            security_str += 'WPA '

        if security & NM_SECURITY_WPA2:
            security_str += 'WPA2 '

        if security & NM_SECURITY_ENTERPRISE:
            security_str += 'ENTERPRISE'

        # Decode our flag into a display string
        input_str = ''
        if user_input == USER_INPUT_NONE:
            input_str = 'NONE'

        if user_input & USER_INPUT_USERNAME:
            input_str += 'USERNAME '

        if user_input & USER_INPUT_PASSWORD:
            input_str += 'PASSWORD '

        print(f'{ap.ssid.decode():15} Flags=0x{ap.flags:X} WpaFlags=0x{ap.wpa_flags:X} RsnFlags=0x{ap.rsn_flags:X} Security={security_str:10} Input={input_str}')




