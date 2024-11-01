# Our main wifi-connect application, which is based around an HTTP server.

import os, getopt, sys, json, atexit
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs
from io import BytesIO
import logging
from logging_journald import JournaldLogHandler, check_journal_stream
from utility import get_config

CONFIG = get_config()

DEBUG = CONFIG['DEBUG'] == 'True'

if (
    # Check if program running as systemd service
    check_journal_stream() or
    # Check if journald socket is available
    JournaldLogHandler.SOCKET_PATH.exists()
):
    LOG_HANDLERS = [JournaldLogHandler(), logging.StreamHandler(sys.stdout)]

logging.basicConfig(level=logging.INFO, handlers=LOG_HANDLERS)
logger = logging.getLogger("wifi-connect")

if DEBUG:
    logger.setLevel(logging.DEBUG)

# Local modules
import netman
import dnsmasq

# Defaults
ADDRESS = '192.168.42.1'
PORT = 80
UI_PATH = '../ui'


#------------------------------------------------------------------------------
# called at exit
def cleanup():
    logger.info("Cleaning up prior to exit.")
    dnsmasq.stop()
    netman.stop_hotspot()


#------------------------------------------------------------------------------
# A custom http server class in which we can set the default path it serves
# when it gets a GET request.
class MyHTTPServer(HTTPServer):
    def __init__(self, base_path, server_address, RequestHandlerClass):
        self.base_path = base_path
        HTTPServer.__init__(self, server_address, RequestHandlerClass)




#------------------------------------------------------------------------------
# A custom http request handler class factory.
# Handle the GET and POST requests from the UI form and JS.
# The class factory allows us to pass custom arguments to the handler.
def RequestHandlerClassFactory(address, ssids):

    class MyHTTPReqHandler(SimpleHTTPRequestHandler):

        def __init__(self, *args, **kwargs):
            # We must set our custom class properties first, since __init__() of
            # our super class will call do_GET().
            self.address = address
            self.ssids = ssids
            try:
                super(MyHTTPReqHandler, self).__init__(*args, **kwargs)
            except ConnectionResetError as e:
                logger.error("Connection reset")


        #suppress sever messages
        def log_message(self, format, *args):
            if not DEBUG:
                return
            else:
                super().log_message(format, *args)

        def de_byte_values(self, object_array):
            """
            check values for byte array and change to string
            """
            output_array = []
            for object in object_array:
                result = {}
                for key, value in object.items():
                    result[key] = value.decode() if isinstance(value, bytes) else value
                output_array.append(result)
            return output_array


        # See if this is a specific request, otherwise let the server handle it.
        def do_GET(self):

            logger.debug(f'do_GET {self.path}')

            # Handle the hotspot starting and a computer connecting to it,
            # we have to return a redirect to the gateway to get the 
            # captured portal to show up.
            if '/hotspot-detect.html' == self.path:
                self.send_response(301) # redirect
                new_path = f'http://{self.address}/'
                logger.debug(f'redirecting to {new_path}')
                self.send_header('Location', new_path)
                self.end_headers()

            if '/generate_204' == self.path:
                self.send_response(301) # redirect
                new_path = f'http://{self.address}/'
                logger.debug(f'redirecting to {new_path}')
                self.send_header('Location', new_path)
                self.end_headers()

            # Handle a REST API request to return the list of SSIDs
            if '/networks' == self.path:
                self.send_response(200)
                self.end_headers()
                response = BytesIO()
                ssids = self.ssids # passed in to the class factory
                """ map whatever we get from net man to our constants:
                Security:
                    NONE         
                    HIDDEN         
                    WEP         
                    WPA        
                    WPA2      
                    ENTERPRISE
                Required user input (from UI form):
                    NONE                   - No input requried.
                    HIDDEN, WEP, WPA, WPA2 - Need password.
                    ENTERPRISE             - Need username and password.
                """
                ssids = self.de_byte_values(ssids)
                response.write(json.dumps(ssids).encode('utf-8'))
                logger.debug(f'GET {self.path} returning: {response.getvalue()}')
                self.wfile.write(response.getvalue())
                return

            # Not sure if this is just OSX hitting the captured portal,
            # but we need to exit if we get it.
            if '/bag' == self.path:
                sys.exit()

            # All other requests are handled by the server which vends files 
            # from the ui_path we were initialized with.
            super().do_GET()


        # test with: curl localhost:5000 -d "{'name':'value'}"
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            self.send_response(200)
            self.end_headers()
            response = BytesIO()
            fields = parse_qs(body.decode('utf-8'))
            logger.debug(f'POST received: {fields}')

            # Parse the form post
            FORM_SSID = 'ssid'
            FORM_HIDDEN_SSID = 'hidden-ssid'
            FORM_USERNAME = 'identity'
            FORM_PASSWORD = 'passphrase'

            if FORM_SSID not in fields:
                logger.error(f'Error: POST is missing {FORM_SSID} field.')
                return

            ssid = fields[FORM_SSID][0]
            password = None
            username = None
            if FORM_HIDDEN_SSID in fields: 
                ssid = fields[FORM_HIDDEN_SSID][0] # override with hidden name
            if FORM_USERNAME in fields: 
                username = fields[FORM_USERNAME][0] 
            if FORM_PASSWORD in fields: 
                password = fields[FORM_PASSWORD][0] 

            # Look up the ssid in the list we sent, to find out its security
            # type for the new connection we have to make
            conn_type = netman.CONN_TYPE_SEC_NONE # Open, no auth AP

            if FORM_HIDDEN_SSID in fields: 
                conn_type = netman.CONN_TYPE_SEC_PASSWORD # Assumption...

            for s in self.ssids:
                if FORM_SSID in s and ssid == s[FORM_SSID] or ssid.encode() == s[FORM_SSID]:
                    if s['security'] == "ENTERPRISE":
                        conn_type = netman.CONN_TYPE_SEC_ENTERPRISE
                    elif s['security'] == "NONE":
                        conn_type = netman.CONN_TYPE_SEC_NONE 
                    else:
                        # all others need a password
                        conn_type = netman.CONN_TYPE_SEC_PASSWORD
                    break

            # Stop the hotspot
            netman.stop_hotspot()

            # Connect to the user's selected AP
            success = netman.connect_to_AP(conn_type=conn_type, ssid=ssid, \
                    username=username, password=password)

            if success:
                response.write(b'OK\n')
            else:
                response.write(b'ERROR\n')
            self.wfile.write(response.getvalue())

            # Handle success or failure of the new connection
            if success:
                logger.info(f'Connected!  Exiting app.')
                sys.exit()
            else:
                logger.warning(f'Connection failed, restarting the hotspot.')

                # Update the list of SSIDs since we are not connected
                self.ssids = netman.get_list_of_access_points()

                # Start the hotspot again
                netman.start_hotspot() 

    return  MyHTTPReqHandler # the class our factory just created.


#------------------------------------------------------------------------------
# Create the hotspot, start dnsmasq, start the HTTP server.
def main(address, port, ui_path, delete_connections, ignore_connections):

    # See if caller wants to delete all existing connections first
    if delete_connections:
        netman.delete_all_wifi_connections()

    #Check if we are already connected, if so we are done.
    if not ignore_connections and netman.have_active_internet_connection():
        print('Already connected to the internet, nothing to do, exiting.')
        sys.exit()

    # Get list of available AP from net man.  
    # Must do this AFTER deleting any existing connections (above),
    # and BEFORE starting our hotspot (or the hotspot will be the only thing
    # in the list).
    ssids = netman.get_list_of_access_points()

    # Start the hotspot
    if not netman.start_hotspot():
        logger.error('Error starting hotspot, exiting.')
        sys.exit(1)

    # Start dnsmasq (to advertise us as a router so captured portal pops up
    # on the users machine to vend our UI in our http server)
    dnsmasq.start()

    # Find the ui directory which is up one from where this file is located.
    web_dir = os.path.join(os.path.dirname(__file__), ui_path)
    logger.info(f'HTTP serving directory: {web_dir} on {address}:{port}')

    # Change to this directory so the HTTPServer returns the index.html in it 
    # by default when it gets a GET.
    os.chdir(web_dir)

    # Host:Port our HTTP server listens on
    server_address = (address, port)

    # Custom request handler class (so we can pass in our own args)
    MyRequestHandlerClass = RequestHandlerClassFactory(address, ssids)

    # Start an HTTP server to serve the content in the ui dir and handle the 
    # POST request in the handler class.
    logger.info(f'Waiting for a connection to our hotspot {netman.get_hotspot_SSID()} ...')
    httpd = MyHTTPServer(web_dir, server_address, MyRequestHandlerClass)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        dnsmasq.stop()
        netman.stop_hotspot()
        httpd.server_close()


#------------------------------------------------------------------------------
# Util to convert a string to an int, or provide a default.
def string_to_int(s, default):
    try:
        return int(s)
    except ValueError:
        return default


#------------------------------------------------------------------------------
# Entry point and command line argument processing.
if __name__ == "__main__":
    atexit.register(cleanup)

    address = ADDRESS
    port = PORT
    ui_path = UI_PATH
    delete_connections = True
    ignore_connections = False

    usage = ''\
f'Command line args: \n'\
f'  -a <HTTP server address>     Default: {address} \n'\
f'  -p <HTTP server port>        Default: {port} \n'\
f'  -u <UI directory to serve>   Default: "{ui_path}" \n'\
f'  -d Delete Connections First  Default: {delete_connections} \n'\
f'  -i Ignore Connections        Default: {ignore_connections} \n'\
f'  -h Show help.\n'

    try:
        opts, args = getopt.getopt(sys.argv[1:], "a:p:u:cdh")
    except getopt.GetoptError:
        logger.error(usage)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print(usage)
            sys.exit()

        elif opt in ("-d"):
           delete_connections = True

        elif opt in ("-a"):
            address = arg

        elif opt in ("-p"):
            port = string_to_int(arg, port)

        elif opt in ("-u"):
            ui_path = arg
        
        elif opt in {"-i"}:
            ignore_connections = True

    logger.info(f'Address={address}')
    logger.info(f'Port={port}')
    logger.info(f'UI path={ui_path}')
    logger.info(f'Delete Connections={delete_connections}')
    logger.info(f'Ignore Connections={ignore_connections}')
    main(address, port, ui_path, delete_connections, ignore_connections)


