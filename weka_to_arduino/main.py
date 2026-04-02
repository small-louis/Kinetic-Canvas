"""Wekinator to Arduino
This script listens for Wekinator OSC messages, and generates both motor
movements as well as LED patterns to send via serial to an Arduino.
"""

import asyncio
import atexit
from asynciolimiter import Limiter

from .osc import Osc
from .wave import WaveSimulation
from .display import PixelDisplay
from .serial import SerialManager
from .touchDesigner import TouchDesignTx, TouchDesignRx
import time
from enum import Enum

frameLimiter = Limiter(10)
enableSerial = False


class AnimationManager:
    last_tick = None
    # Landscape orientation
    res_y = 21
    res_x = 8
    # res_x = 16
    # res_y = 1
    num_motors = 21
    # baud_rate = 921600
    # baud_rate = 460800
    baud_rate = 115200
    # baud_rate = 57600

    def __init__(self):
        self.wave: WaveSimulation = WaveSimulation(self)
        self.display: PixelDisplay = PixelDisplay(self, 60, 20)
        # self.serial: SerialManager = SerialManager(self, 460800, "/dev/cu.usbmodem1201")
        # self.serial: SerialManager = SerialManager(self, 115200)
        # self.serial: SerialManager = SerialManager(self, 921600)
        self.serial: SerialManager = (
            SerialManager(self, self.baud_rate) if enableSerial else None
        )
        # self.osc: Osc = Osc(self)
        self.touchTx: TouchDesignTx = TouchDesignTx(self)
        self.touchRx: TouchDesignRx = TouchDesignRx(self)

    async def start(self):
        # await self.osc.start()
        await self.wave.setup_plot()
        # await self.display.setup()
        if enableSerial:
            await self.serial.setup()
        await self.touchTx.setup()
        await self.touchRx.setup()

        self.running = True
        self.last_tick = time.monotonic()
        while self.running:
            try:
                await self.tick()
            except KeyboardInterrupt:
                self.running = False
        else:
            self.stop()

    async def stop(self):
        self.running = False
        # await self.osc.stop()
        if enableSerial:
            await self.serial.stop()
        asyncio.get_event_loop().stop()

    async def tick(self):
        # Limit the frame rate
        await frameLimiter.wait()
        # Calculate the time since the last tick
        # delta_time = time.monotonic() - self.last_tick
        delta_time = 0.10
        self.last_tick = time.monotonic()

        # Handle subclass ticks (OSC, etc)
        # await self.osc.tick()  # Get OSC messages

        # Update the wave simulation
        self.wave.tick(delta_time)

        # Send the wave data to TouchDesigner
        await self.touchTx.tick()

        # Get data from TouchDesigner
        await self.touchRx.tick()

        # # Handle updating the display
        # await self.display.tick()

        # Send the data to the Arduino
        if enableSerial:
            await self.serial.tick()


if __name__ == "__main__":
    manager = AnimationManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(manager.start())
    atexit.register(manager.stop)
