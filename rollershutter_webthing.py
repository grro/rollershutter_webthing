import tornado.ioloop
from webthing import (Property, Thing, Value)
from rollershutter import Shutter



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
        self.shutter.register_listener(self.on_value_changed)

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

        self.position = Value(shutter.position, shutter.set_position)
        self.add_property(
            Property(self,
                     'position',
                     self.position,
                     metadata={
                         '@type': 'LevelProperty',
                         'title': 'position',
                         "type": "number",
                         "minimum": 0,
                         "maximum": 100,
                         "unit": "percent",
                         'description': 'the position in percent [0..100]',
                         'readOnly': False,
                     }))


    def on_value_changed(self, shutter: Shutter):
        self.ioloop.add_callback(self._on_value_changed)

    def _on_value_changed(self):
        self.position.notify_of_external_update(self.shutter.position)



# test curl
# curl -X PUT -d '{"position": 40}' http://localhost:9955/0/properties/position