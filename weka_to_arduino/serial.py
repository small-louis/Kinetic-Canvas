import asyncio
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main import AnimationManager

from serial.tools import list_ports
from serial import Serial
from cobs import cobs
from crc import Calculator, Crc8
import numpy as np

calculator = Calculator(Crc8.CCITT)


class SerialManager:
    def __init__(self, manager: "AnimationManager", baudrate, port=None):
        self.manager = manager
        self.port = port
        self.baudrate = baudrate
        ports = list_ports.comports()
        print("Available ports: ", [p.description for p in ports])
        if port == None:
            matchingBoards = list_ports.grep("usb(?:serial|modem)|CP2102|Arduino")
            boardList = list(matchingBoards)
            if len(boardList) == 0:
                raise Exception("No matching boards found")
            self.port = boardList[0].device
            print(f"Using port: {boardList[0]}")
        self.serial = Serial(self.port, self.baudrate, timeout=1)

    async def setup(self):
        # return self.serial
        print(f"Serial State: {self.serial.is_open}")
        print("Starting self-test...")
        for i in range(self.manager.wave.servo_count):
            self.set_motor(i, self.manager.wave.gM_0[i], instant=True, log=True)
        print("Motors moved to initial positions.")
        await asyncio.sleep(3)
        # for i in range(self.manager.wave.servo_count):
        #     self.set_motor(i, 0, self.manager.wave.gM_0[i] - 3, log=True)
        # print("Motors moved to 10 degrees.")
        print("Self-test complete.")
        await asyncio.sleep(1)

    async def stop(self):
        self.serial.close()

    bytesSinceLastTick = 0
    buffer_size = 64
    buffer = bytearray(buffer_size)
    buffer_pos = 0

    def logAnyMessages(self):
        if self.serial.in_waiting:
            print("[SERIAL] ")
            while self.serial.in_waiting:
                try:
                    print(self.serial.read_until())
                except Exception as e:
                    print(f"Error reading serial: {e}")

    def sendBytes(self, data: bytearray):
        if len(data) + self.buffer_pos > self.buffer_size:
            # Send the buffer now
            self.serial.write(self.buffer)
            buffer = bytearray(self.buffer_size)
            self.buffer_pos = 0
        self.buffer[self.buffer_pos : self.buffer_pos + len(data)] = data
        self.buffer_pos += len(data)
        self.bytesSinceLastTick += len(data)

    def sendBytesNow(self, data: bytearray):
        # Wait for the buffer to clear if it's full
        if len(data) > self.buffer_size:
            raise Exception("Data too large for buffer")
        while self.serial.out_waiting > self.buffer_size + len(data) - 2:
            pass
        self.serial.write(data)
        self.bytesSinceLastTick += len(data)

    def sendCommand(self, mode: 0 | 1, index: int, value: int, instant=False):
        """Handle all the low-level comms with the Arduino"""
        # Schema: 2 byte for command and motor/pixel number, 1 byte for data, 1 byte for checksum
        # Command first bit: 0 - Motor, 1 - Pixel
        # Command rest of the bits: Motor or Pixel number
        # Data: 0 - 255
        # Checksum: CRC8 on the command and data
        command = index
        if mode == 1:
            command = index | 0x8000
        data = int(np.clip(value, 0, 255))
        combinedBytes = struct.pack(">HB", command, data)
        checksum = calculator.checksum(combinedBytes)
        preEncode = combinedBytes + struct.pack(">B", checksum)
        encoded = cobs.encode(preEncode)
        if instant:
            self.sendBytesNow(encoded + b"\x00\x00\x00")
        else:
            self.sendBytes(encoded + b"\x00\x00\x00")

    def set_motor(self, index: int, angle: int, instant=False, log=False):
        """Set the angle of a motor"""
        self.sendCommand(0, index, angle, instant=instant)
        if log:
            print(f"Sent motor {index} with angle {angle}deg")
            self.logAnyMessages()

    def set_pixel(self, index: int, rgb: int, instant=False, log=False):
        """Set the RGB value of a pixel (RGB is encoded as a single int)"""
        self.sendCommand(1, index, rgb, instant=instant)
        if log:
            print(f"Sent pixel {index} with value {rgb}")
            self.logAnyMessages()

    async def tick(self):
        # Start by ensuring we're beginning with a new packet
        self.sendBytes(b"\x00\x00\x00\x00\x00")
        # # See if there's anything to read
        # self.logAnyMessages()
        # Create bytes for motor
        motors = [int(i) for i in self.manager.wave.calculate_servo_angles()]
        # Create bytes for pixels
        pixels = self.manager.touchRx.pixel_data_233
        pixelBytes = pixels.flatten()
        # Send data

        # Send motor data
        for i, motor in enumerate(motors):
            self.set_motor(i, motor, instant=True)
        # # Send pixel data
        for i, pixel in enumerate(pixelBytes):
            self.set_pixel(i, pixel, instant=True)
        # Finally, send gradient index
        self.sendCommand(
            1,
            600,
            int(np.clip(0 - 30, 0, 255)),
            instant=True,
        )
        # self.sendCommand(
        #     1,
        #     600,
        #     int(np.clip(self.manager.osc.gradient_index - 30, 0, 255)),
        #     instant=True,
        # )
        # self.sendCommand(
        #     1,
        #     600,
        #     int(np.clip(self.manager.osc.gradient_index - 30, 0, 255)),
        #     instant=True,
        # )
        # print(int(np.clip(self.manager.osc.gradient_index - 30, 0, 255)))
