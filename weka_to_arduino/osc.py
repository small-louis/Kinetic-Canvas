# This python handles OSC commands. It listens to the port 12000 and prints the received messages.
import math
import time
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main import AnimationManager


class Osc:
    def __init__(self, manager: "AnimationManager"):
        # Reference to the AnimationManager instance
        self.gradient_index = 0
        self.manager = manager
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/wek/outputs", self.print)
        host = ("127.0.0.1", 12000)
        self.server = AsyncIOOSCUDPServer(
            host, self.dispatcher, asyncio.get_event_loop()
        )
        self.wave_initials = [
            (wave.amplitude, wave.period) for wave in self.manager.wave.waves
        ]
        print("Listening for Wekinator on {}".format(host))

    last_message_time = time.time()
    history = []
    window_size = 50

    def get_osc_wave(self):
        return self.manager.wave.waves[0]

    def print(self, address, amplitude, frequency, *args):
        # print(f"{address}: {round(amplitude,2)}, {round(frequency,2)}")
        # Attempt to set values of WaveSimulation Wave 1
        try:
            # Update last message time
            self.last_message_time = time.time()
            if len(self.history) < self.window_size:
                # Fill start with current values
                current = self.get_osc_wave()
                self.history = [(current.amplitude, current.period)] * self.window_size
            self.history.append((max(amplitude, 0) * 10, max(frequency, 0) * 10 + 8))
            # print(
            #     f"Wave 1: {self.get_osc_wave().amplitude}, {self.get_osc_wave().period}"
            # )
            # self.get_osc_wave().speed = speed
        except:
            pass

    async def tick(self):
        # This needs to be called in the main loop
        # If no messages have been received in the last 5 seconds, start fading out the wave
        delta = time.time() - self.last_message_time
        if delta > 0.5:
            self.history = []
            if delta > 5:
                # print("Fading out wave")
                self.get_osc_wave().amplitude = max(
                    self.get_osc_wave().amplitude * 0.95 - 0.1, 0
                )
                # Slowly blend gradient back to index 0
                self.gradient_index = max(self.gradient_index * 0.95 - 1, 0)
                # Blend back in original waves
                for i, wave in enumerate(self.manager.wave.waves):
                    if wave != self.get_osc_wave():
                        wave.amplitude = (
                            wave.amplitude * 0.95 + self.wave_initials[i][0] * 0.05
                        )
                        # wave.period = (
                        #     wave.period * 0.95 + self.wave_initials[i][1] * 0.05
                        # )
            else:
                # Still increase gradient index
                self.gradient_index = min(self.gradient_index + 1, 255)
        else:
            # Get average of last 10 messages
            if len(self.history) >= 10:
                amplitude = (
                    sum([x[0] for x in self.history[-self.window_size :]])
                    / self.window_size
                )
                # frequency = (
                #     sum([x[1] for x in self.history[-self.window_size :]])
                #     / self.window_size
                # )
                frequency = 9
                self.get_osc_wave().amplitude = amplitude
                self.get_osc_wave().period = frequency
                for wave in self.manager.wave.waves:
                    if wave != self.get_osc_wave():
                        wave.amplitude = max(wave.amplitude * 0.95 - 0.1, 0)
                # As time goes on, we will ease increase self.gradient_index to show progress, up to a maximum of 255
                # self.gradient_index = min(self.gradient_index + 8, 255)
                self.gradient_index = min(self.gradient_index + amplitude, 255)

        await asyncio.sleep(0)

    async def start(self):
        self.transport, self.protocol = (
            await self.server.create_serve_endpoint()
        )  # Create datagram endpoint and start serving

    async def stop(self):
        if self.transport:
            self.transport.close()
