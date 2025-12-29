from typing import List
from mcp_server import MCPServer
from rollershutter import Shutter


class RollershutterMCPServer(MCPServer):

    def __init__(self, name: str, port: int, rollershutters: List[Shutter]):
        super().__init__(name, port)
        self.rollershutters = rollershutters


        @self.mcp.resource("rollershutter://list/names")
        def list_shutter_names() -> str:
            """Returns a comma-separated list of all available rollershutter names."""
            return ", ".join([shutter.name for shutter in self.rollershutters])


        @self.mcp.resource("rollershutter://{shuttername}/position")
        def get_position(shuttername: str) -> str:
            """
            Returns the current position of a specific rollershutter.
            0 = fully open, 100 = fully closed.
            """
            for shutter in self.rollershutters:
                if shutter.name == shuttername:
                    return str(shutter.position())
            raise ValueError(f"shutter '{name}' not found")


        @self.mcp.tool()
        def set_position(name: str, position: int) -> str:
            """
            Moves a specific rollershutter to a target position.
            :param name: The name of the shutter (e.g., 'Kitchen')
            :param position: Target position from 0 (open) to 100 (closed)
            """
            shutter = next((s for s in self.rollershutters if s.name == name), None)
            if shutter is None:
                return f"Error: Rollershutter '{name}' was not found."

            if not (0 <= position <= 100):
                return "Error: Position must be an integer between 0 and 100."

            # Execute the movement
            shutter.set_position(position)
            return f"Success: {name} is moving to {position}%."


# npx @modelcontextprotocol/inspector
