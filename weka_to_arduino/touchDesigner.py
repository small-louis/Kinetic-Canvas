# This file attempts to communicate the wave data to TouchDesigner
import asyncio
from .wave import WaveSimulation

import numpy as np
from typing import TYPE_CHECKING
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

if TYPE_CHECKING:
    from .main import AnimationManager


class TouchDesignRx:
    """Handle the pixel data coming back from TouchDesigner"""

    def __init__(self, manager: "AnimationManager") -> None:
        self.manager = manager
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/rgb", self.parse_frame)
        host = ("127.0.0.1", 10001)
        self.server = AsyncIOOSCUDPServer(
            host, self.dispatcher, asyncio.get_event_loop()
        )
        print("Listening for TouchDesigner on {}".format(host))
        # self.pixel_data = np.zeros((self.manager.res_x, self.manager.res_y, 3))
        # self.pixel_data_raw = [0] * (self.manager.res_x * self.manager.res_y * 3)
        self.pixel_data_raw = [0] * (self.manager.res_x)
        self.pixel_data_233 = np.zeros((self.manager.res_x, self.manager.res_y))

    def parse_frame(self, address, *args):
        # print(f"Got RGB message! Length: {len(args)}")
        if len(args) != self.manager.res_x * self.manager.res_y:
            print(
                f"Had {len(args)} pixels, expected {self.manager.res_x * self.manager.res_y}"
            )
            return
        # print(f"Got RGB message! Length: {len(args)}")
        self.pixel_data_raw = [int(i) for i in args]
        # Option 1: Send full color data
        # # Reshape for easier ops
        # self.pixel_data = np.array(args).reshape(
        #     (self.manager.res_x, self.manager.res_y, 3)
        # )
        # # Convert 0-255 to 2-3-3 bit RGB
        # # byte red = (originalColor.red * 8) / 256;
        # # byte green = (originalColor.green * 8) / 256;
        # # byte blue = (originalColor.blue * 4) / 256;
        # # Convert to 2-3-3 single integer (0-255) in a 2d array
        # for i in range(self.manager.res_x):
        #     for j in range(self.manager.res_y):
        #         r, g, b = self.pixel_data[i, j]
        #         self.pixel_data_233[i, j] = (
        #             int((r * 8) // 256) << 5
        #             | int((g * 8) // 256) << 2
        #             | int((b * 4) // 256)
        #         )
        #         # if i == 0 and j == 0:
        #         #     print(f"R: {r}, G: {g}, B: {b}, 233: {self.pixel_data_233[i, j]}")
        # Option 2: Send Grayscale data
        self.pixel_data_233 = np.array(self.pixel_data_raw)

    async def tick(self):
        # This needs to be called in the main loop
        await asyncio.sleep(0)

    async def setup(self):
        self.transport, self.protocol = (
            await self.server.create_serve_endpoint()
        )  # Create datagram endpoint and start serving

    async def stop(self):
        if self.transport:
            self.transport.close()


class TouchDesignTx:
    """Send wave data to TouchDesigner"""

    def __init__(self, manager: "AnimationManager", host=("127.0.0.1", 10000)) -> None:
        self.manager = manager
        self.client = SimpleUDPClient(*host)

    async def setup(self):
        self.client.send_message(
            "/resolution",
            [
                # Send in Y, X order as we want to have a landscape orientation
                self.manager.res_y,
                self.manager.res_x,
            ],
        )

    async def stop(self):
        pass

    async def tick(self):
        _x_pos, wave_pos = self.manager.wave.calculate_discrete_positions(
            self.manager.res_x * 30  # x30 to provide more high frequency data
        )
        wave_norm = np.interp(wave_pos, (-20, 20), (0, 1))
        self.client.send_message("/wave", wave_norm)
        self.client.send_message(
            "/resolution",
            [
                self.manager.res_y,
                self.manager.res_x,
            ],
        )
