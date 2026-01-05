from typing import List
from mcp_server import MCPServer
from rollershutter import Shutter


class RollershutterMCPServer(MCPServer):

    def __init__(self, name: str, port: int, rollershutters: List[Shutter]):
        super().__init__(name, port)
        self.rollershutters = rollershutters

        @self.mcp.tool()
        def set_position(name: str, position: int) -> str:
            """
            Moves a specific rollershutter or all shutters to a target position.
            Orientation:
            0 = FULLY OPEN (Sunshine/Daylight).
            100 = FULLY CLOSED (Privacy/Night mode).

            :param name: The name of the shutter (e.g., 'Kitchen') or 'all' to move everything.
            :param position: Target position from 0 (open) to 100 (closed).
            """
            # Logic for 'all' group
            if name.lower() == "all":
                for s in self.rollershutters:
                    s.set_position(position)
                return f"Success: All shutters are moving to {position}%."

            # Logic for individual shutters
            shutter = next((s for s in self.rollershutters if s.name == name), None)
            if shutter is None:
                return f"Error: Rollershutter '{name}' not found. Available: {[s.name for s in self.rollershutters]}"

            if not (0 <= position <= 100):
                return "Error: Position must be between 0 (open) and 100 (closed)."

            # Execute the movement
            shutter.set_position(position)
            return f"Success: {name} is moving to {position}%."

        @self.mcp.tool()
        def get_system_status() -> str:
            """
            Provides a summary of all rollershutters and their current positions.
            Use this tool when the user asks 'Are the shutters closed?' or 'What is the status?'.
            """
            status_list = [f"{s.name}: {s.position}%" for s in self.rollershutters]
            return "Current Status: " + " | ".join(status_list)

# npx @modelcontextprotocol/inspector

