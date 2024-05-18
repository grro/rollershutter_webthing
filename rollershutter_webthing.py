import sys
import logging
import tornado.ioloop
from typing import Dict
from webthing import (MultipleThings, Property, Thing, Value, WebThingServer)
from rollershutter import Shutter, RollerShutter, RollerShutters




class RollerShutterThing(Thing):

    # regarding capabilities refer https://iot.mozilla.org/schemas
    # there is also another schema registry http://iotschema.org/docs/full.html not used by webthing

    def __init__(self, description: str, shutter: Shutter):
        Thing.__init__(
            self,
            'urn:dev:ops:rollershutter-1',
            'rollershutter_' + shutter.name,
            ['MultiLevelSensor'],
            description
        )
        self.ioloop = tornado.ioloop.IOLoop.current()
        self.shutter = shutter
        self.shutter.add_listener(self.on_value_changed)

        self.name = Value(shutter.name)
        self.add_property(
            Property(self,
                     'name',
                     self.name,
                     metadata={
                         'title': 'name',
                         "type": "string",
                         'description': 'the shutter name',
                         'readOnly': True,
                     }))

        self.position = Value(shutter.position)
        self.add_property(
            Property(self,
                     'position',
                     self.position,
                     metadata={
                         'title': 'position',
                         "type": "int",
                         'description': 'the position in percent [0..100]',
                         'readOnly': False,
                     }))


    def on_value_changed(self):
        self.ioloop.add_callback(self._on_value_changed)

    def _on_value_changed(self):
        self.position.notify_of_external_update(self.shutter.position)


def run_server(description: str, port: int, name: str, name_address_map: Dict[str, str]):
    if len(name_address_map) < 2:
        shutters = [RollerShutter(name, name_address_map[dev_name]) for dev_name in name_address_map.keys()]
    else:
        shutters = [RollerShutter(name + "_" + dev_name, name_address_map[dev_name]) for dev_name in name_address_map.keys()]
        shutters = [RollerShutters(name + "_all", shutters)] + shutters
    shutters_tings = [RollerShutterThing(description, shutter) for shutter in shutters]
    server = WebThingServer(MultipleThings(shutters_tings, name), port=port, disable_host_validation=True)
    try:
        logging.info('starting the server http://localhost:' + str(port))
        [shutter.start() for shutter in shutters]
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping the server')
        [shutter.stop() for shutter in shutters]
        server.stop()
        logging.info('done')



def parse_devices(config: str) -> Dict[str, str]:
    name_address_map = {}
    for device in config.split("&"):
        name, address = device.split('=')
        name_address_map[name.strip()] = address.strip()
    return name_address_map


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(name)-20s: %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger('tornado.access').setLevel(logging.ERROR)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    run_server("description", int(sys.argv[1]), sys.argv[2], parse_devices(sys.argv[3]))
