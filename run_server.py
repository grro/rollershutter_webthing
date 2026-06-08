import sys
import logging
from time import sleep
from typing import List, Dict
from webthing import (MultipleThings, WebThingServer)

from rollershutter import RollerShutter, RollerShutters
from rollershutter_web import RollershutterWebServer
from rollershutter_mcp import RollershutterMCPServer
from rollershutter_webthing import RollerShutterThing



def run_server(description: str, port: int, name: str, name_address_map: Dict[str, str], reverse_directions: bool):
    shutters : List[RollerShutter] = None
    if len(name_address_map) < 2:
        shutters = [RollerShutter(name, name_address_map[dev_name], reverse_directions=reverse_directions) for dev_name in name_address_map.keys()]
    else:
        shutters = [RollerShutter(name + "_" + dev_name, name_address_map[dev_name], reverse_directions=reverse_directions) for dev_name in name_address_map.keys()]
        shutters = [RollerShutters(name + "_all", shutters)] + shutters

    web_server = RollershutterWebServer(shutters, port=port+1)
    mcp_server = RollershutterMCPServer(name, port+2, shutters)
    server = WebThingServer(MultipleThings( [RollerShutterThing(description, shutter) for shutter in shutters], name), port=port, disable_host_validation=True)
    try:
        [shutter.start() for shutter in shutters]
        web_server.start()
        mcp_server.start()
        logging.info('starting the server http://localhost:' + str(port))
        server.start()
        sleep(10000)
    except KeyboardInterrupt:
        logging.info('stopping the server')
        [shutter.stop() for shutter in shutters]
        web_server.stop()
        mcp_server.stop()
        server.stop()
        logging.info('done')



def parse_devices(config: str) -> Dict[str, str]:
    name_address_map = {}
    for device in config.split("&"):
        name, address = device.split('=')
        address = address.strip()
        if address.endswith('/'):
            address = address[:-1]
        name_address_map[name.strip()] = address
    return name_address_map


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(name)-20s: %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger('tornado.access').setLevel(logging.ERROR)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)
    run_server("description", int(sys.argv[1]), sys.argv[2], parse_devices(sys.argv[3]), sys.argv[4].strip().lower() == 'true')

