# python-sdbus-wifi-connect
This is a verions of [python-wifi-connect](https:https://github.com/OpenAgricultureFoundation/python-wifi-connect.git) that uses the more recent [sdbus-networkmanager](https://github.com/python-sdbus/python-sdbus-networkmanager.git) library

Inspired by the [wifi-connect](https://github.com/balena-io/wifi-connect) project written by [balena.io](https://www.balena.io/).  

It has been tested on Raspbery Pi 4 running  Debian GNU/Linux 12 (bookworm), Kernel 6.6.31+rpt-rpi-v8 and Python 3.11.2

For your particular application, replace the logo.svg and favicon.ico files in the ui/img folder.  If you only have a png of your logo, place it in the above folder and modify line 38 of the index.html file accordingly.

### All these scripts must be run as root (or via sudo)

# Install and Run

Please read the [INSTALL.md](INSTALL.md) then the [RUN.md](RUN.md) files.


# How it works
![How it works](./docs/images/how-it-works.png?raw=true)

WiFi Connect interacts with NetworkManager, which should be the active network manager on the device's host OS.

### 1. Advertise: Device Creates Access Point

WiFi Connect detects available WiFi networks and opens an access point with a captive portal. Connecting to this access point with a mobile phone or laptop allows new WiFi credentials to be configured.

### 2. Connect: User Connects Phone to Device Access Point

Connect to the opened access point on the device from your mobile phone or laptop. The access point SSID is, by default, `<name>` where "name" is something random like "shy-lake" or "green-frog" or "dawnlite" (what is currently in the codebase). 

### 3. Portal: Phone Shows Captive Portal to User

After connecting to the access point from a mobile phone, it will detect the captive portal and open its web page. Opening any web page will redirect to the captive portal as well.

### 4. Credentials: User Enters Local WiFi Network Credentials on Phone

The captive portal provides the option to select a WiFi SSID from a list with detected WiFi networks and enter a passphrase for the desired network.

### 5. Connected!: Device Connects to Local WiFi Network

When the network credentials have been entered, WiFi Connect will disable the access point and try to connect to the network. If the connection fails, it will enable the access point for another attempt. If it succeeds, the configuration will be saved by NetworkManager.

# Details
* [Video demo of the application.](https://www.youtube.com/watch?v=TN7jXMmKV50)
* [These are the geeky development details and background on this application.](docs/details.md)

# Additions

- The files in the nm_scripts directory are standalone and can be used to manipulate connections
- The *run.sh* script executes the primary program: *http_server.py*.
- The *install.sh* script creates a virtual environment and loads all needed modules.

- To allow for other services to recognize the state of the Raspberry Pi, in hotspot mode, the file:

  - */etc/wifi_state/hotspot*

- exists.  Otherwise, the file

  - */etc/wifi_state/client*

- exists

- Added the -i option to the *http_server.py* program to allow the user to ignore a *eth0* connection while doing 
development work.  The program will still manipulate the wlan0 connections.

- net_man_utlites.py has been removed as all of its functions can be accomplished with nmcli



