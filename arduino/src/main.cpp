#include <Arduino.h>
#include <CRC8.h>
#include <PacketSerial.h>
#include <FastLED.h>
#include <ESP32Servo.h>
#include <HardwareSerial.h>
#include "soc/rtc_wdt.h"
#include <Ewma.h>
#include <vector> // Include this header to use std::vector

// Define
// #define BAUD_RATE 460800
// #define BAUD_RATE 921600
#define BAUD_RATE 115200
// #define SERIAL_SIZE_RX 1024
// #define BAUD_RATE 57600
#define NUM_MOTORS 14 // The total number of motors
#define NUM_LEDS 168
#define PIXEL_DATA_PIN 13
#define LED_TYPE WS2815

// Create array of EWMA objects - one for each motor. Value = 0.1
std::vector<Ewma> motorEwma;

// Move serial to second CPU core
TaskHandle_t SerialTaskHandle;
TaskHandle_t OutputTaskHandle;

PacketSerial DaughterSerial;

// Lighting
CRGB leds[NUM_LEDS];
CRGBPalette16 currentPalette;
TBlendType currentBlending;
uint8_t gradientIndex = 0;
#include <FastLED.h>

DEFINE_GRADIENT_PALETTE(myGradientPalette){
		0, 218, 232, 255, // rgba(218,232,255,1) at 0%
		7, 62, 195, 219,	// rgba(62,195,219,1) at 7%
		13, 0, 150, 224,	// rgba(0,150,224,1) at 13%
		21, 0, 58, 172,		// rgba(0,58,172,1) at 21%
		26, 0, 0, 139,		// rgba(0,0,139,1) at 26%
		34, 75, 13, 132,	// rgba(75,13,132,1) at 34%
		40, 132, 22, 120, // rgba(132,22,120,1) at 40%
		46, 162, 8, 83,		// rgba(162,8,83,1) at 46%
		53, 198, 0, 57,		// rgba(198,0,57,1) at 53%
		60, 255, 0, 0,		// rgba(255,0,0,1) at 60%
		66, 255, 0, 0,		// rgba(255,0,0,1) at 66%
		73, 255, 42, 42,	// rgba(255,42,42,1) at 73%
		80, 255, 61, 61,	// rgba(255,61,61,1) at 80%
		85, 228, 18, 18,	// rgba(228,18,18,1) at 85%
		91, 138, 17, 17,	// rgba(138,17,17,1) at 91%
		100, 130, 33, 33, // rgba(130,33,33,1) at 100%
		255								// End of palette
};

CRGBPalette256 BlueRedGradient = myGradientPalette;

// Motors
int motorAngles[NUM_MOTORS];
// const int motorPins[NUM_MOTORS] = {12};
const int motorPins[NUM_MOTORS] = {
		// Bundle one
		12,
		14,
		27,
		26,
		25,
		33,
		32,
		// Bundle two
		15,
		2,
		4,
		5,
		18,
		19,
		21};
Servo servos[NUM_MOTORS];

// Serial
CRC8 crc;
PacketSerial mainSerial;

void sendPacket(uint16_t command, uint8_t data)
{
	uint8_t buffer[4];
	buffer[0] = (command >> 8);
	buffer[1] = command & 0xFF;
	buffer[2] = data;
	crc.reset();
	crc.add(buffer[0]);
	crc.add(buffer[1]);
	crc.add(buffer[2]);
	buffer[3] = crc.calc();
	if (DEBUG_MODE)
	{
		Serial.print("Sending Downstream:");
		for (int i = 0; i < 4; i++)
		{
			Serial.print(buffer[i], HEX);
			Serial.print(" ");
		}
		Serial.println();
	}
	DaughterSerial.send(buffer, 4);
}

void onPacketReceived(const uint8_t *buffer, size_t size)
{
	// if (DEBUG_MODE)
	// {

	// 	Serial.println("Packet received");
	// }
	if (size != 4)
	{
		return;
	}
	// Move to temp buffer in case we need to modify it
	if (DEBUG_MODE)
	{
		Serial.println("Reading into memory...");
		// Log packet in hex codes
		Serial.print("Packet:");
		for (int i = 0; i < size; i++)
		{
			Serial.print(buffer[i], HEX);
			Serial.print(" ");
		}
		Serial.println();
	}
	uint8_t tempBuffer[size];
	memcpy(tempBuffer, buffer, size);
	// if (DEBUG_MODE)
	// {
	// 	Serial.println("Done reading into memory...");
	// }

	uint16_t command = ((unsigned short)tempBuffer[0] << 8) | (unsigned char)tempBuffer[1];
	uint16_t index = (((unsigned short)tempBuffer[0] & 0x7F) << 8) | (unsigned char)tempBuffer[1];
	uint8_t data = tempBuffer[2];
	uint8_t checksum = tempBuffer[3];

	crc.reset();
	crc.add(tempBuffer[0]);
	crc.add(tempBuffer[1]);
	crc.add(tempBuffer[2]);
	uint8_t calculatedChecksum = crc.calc();
	if (checksum != calculatedChecksum)
	{
		if (DEBUG_MODE)
		{
			Serial.print("FAIL: ");
			Serial.print(checksum);
			Serial.print(" != (calc) ");
			Serial.print(calculatedChecksum);
			Serial.print(" (command) ");
			Serial.print(command);
			Serial.print(". Data: ");
			Serial.print(data);
			Serial.print(". Packet:");
			for (int i = 0; i < size; i++)
			{
				// Print the byte in binary
				for (int j = 7; j >= 0; j--)
				{
					bool is = (tempBuffer[i] >> j) & 1;
					if (is)
					{
						Serial.print("1");
					}
					else
					{
						Serial.print("0");
					}
				}
				Serial.print(" ");
			}
			Serial.println();
		}
		return;
	}

	if (tempBuffer[0] & 0x80)
	{
		// Pixel
		int pixel = index;
		if (pixel >= NUM_LEDS)
		{
			if (pixel > 512)
			{
				// This value will set our index in the gradient above
				gradientIndex = data;
				if (DEBUG_MODE)
				{
					// Log command
					Serial.print("Gradient set to ");
					Serial.println(gradientIndex);
				}
				return;
			}
			else
			{
				// Pixel out of range, something is wrong
				return;
			}
		}
		if (DEBUG_MODE && pixel == 1)
		{
			// Log command
			Serial.print("Pixel ");
			Serial.print(index);
			Serial.print(" set to ");
			Serial.println(data);
			// Log original packet
			Serial.print("^Packet:");
			for (int i = 0; i < size; i++)
			{
				Serial.print(tempBuffer[i], HEX);
				Serial.print(" ");
			}
			Serial.println();
		}
		// leds[pixel] = ColorFromPalette(currentPalette, 0, data, currentBlending);
		leds[pixel] = ColorFromPalette(currentPalette, min(max(data / 20 - 6 + gradientIndex, 0), 255), data, currentBlending);
		// leds[pixel] = CRGB(data, data, data);
		// if (pixel == 0)
		// {
		// 	FastLED.show();
		// }
	}
	else
	{
		// Motor
		int motor = command;
		if (motor >= NUM_MOTORS)
		{
			// Attempt to pass on to daughter board
			if (Serial2)
			{
				sendPacket(command - NUM_MOTORS, data);
			}
		}
		motorAngles[motor] = data;
		// set_motor(motor, data);
		// motorAngles[motor] = data;
		// Log new motor angle
		if (DEBUG_MODE)
		{
			Serial.print("Motor ");
			Serial.print(motor);
			Serial.print(" set to ");
			Serial.println(data);
		}
	}
}

void setupSerial(void *pvParameters)
{
	// Serial.setRxBufferSize(SERIAL_SIZE_RX);

	while (!Serial)
	{
		vTaskDelay(pdMS_TO_TICKS(10));
		; // Wait for serial port to connect. Needed for native USB port only
	}
	// Start listening
	mainSerial.setPacketHandler(&onPacketReceived);
	for (;;)
	{
		mainSerial.update();
		if (mainSerial.overflow())
		{
			// Set the LED to high to indicate an overflow.
			// digitalWrite(LED_BUILTIN, HIGH);
		}
		rtc_wdt_feed();
		EVERY_N_MILLISECONDS(1000)
		{
			// Delay to prevent CPU overload
			vTaskDelay(pdMS_TO_TICKS(10));
		}
	}
}

void setupMainLoop(void *pvParameters)
{
	for (;;)
	{
		EVERY_N_MILLISECONDS(20)
		{
			// Example animation to test lighting
			FastLED.show();
			// servos[motor].write(data);
			for (int i = 0; i < NUM_MOTORS; i++)
			{
				// if (DEBUG_MODE)
				// {
				// 	Serial.print("!!Motor ");
				// 	Serial.print(i);
				// 	Serial.print(" set to ");
				// 	Serial.println(motorAngles[i]);
				// }
				servos[i].write(motorEwma[i].filter(motorAngles[i]));
			}
		}
		rtc_wdt_feed();
		EVERY_N_MILLISECONDS(1000)
		{
			// Delay to prevent CPU overload
			vTaskDelay(pdMS_TO_TICKS(10));
		}
	}
}

void setup()
{
	delay(2000);

	// Setup Listening Serial
	mainSerial.begin(BAUD_RATE);
	// Set up Second serial port
	// RX = 16, TX = 17
	Serial2.begin(BAUD_RATE, SERIAL_8N1, 16, 17);
	DaughterSerial.setStream(&Serial2);

	if (DEBUG_MODE)
	{
		Serial.println("Serial setup complete");
	}
	// Setup Lighting
	// 		.setCorrection(TypicalLEDStrip);
	// FastLED.addLeds<WS2812B, PIXEL_DATA_PIN, GRB>(leds, NUM_LEDS);
	FastLED.addLeds<WS2815, PIXEL_DATA_PIN>(leds, NUM_LEDS);
	FastLED.setMaxRefreshRate(10, true);
	currentPalette = BlueRedGradient;
	currentBlending = LINEARBLEND;
	// Setup motors
	// servos[0].setPeriodHertz(50); // Standard 50hz servo
	for (int i = 0; i < NUM_MOTORS; ++i)
	{
		motorEwma.emplace_back(0.5);
	}
	for (int i = 0; i < NUM_MOTORS; i++)
	{
		// servos[i].attach(motorPins[i], 1000, 2000);
		servos[i].attach(motorPins[i]);
		if (i % 2 == 0)
		{
			motorAngles[i] = motorEwma[i].filter(65);
			servos[i].write(motorAngles[i]);
		}
		else
		{
			motorAngles[i] = motorEwma[i].filter(37);
			servos[i].write(motorAngles[i]);
		}
		delay(100);
	}
	if (DEBUG_MODE)
	{

		// Serial.println("Setting motors to G_0 + 5");
		// for (int i = 0; i < NUM_MOTORS; i++)
		// {
		// 	if (i % 2 == 0)
		// 	{
		// 		servos[i].write(70);
		// 	}
		// 	else
		// 	{
		// 		servos[i].write(32);
		// 	}
		// 	delay(100);
		// }
		delay(2000);
	}
	if (DEBUG_MODE)
	{

		Serial.println("Setting motors to G_0");
	}
	// - Set motors to G_0
	// for (int i = 0; i < NUM_MOTORS; i++)
	// {
	// 	if (i % 2 == 0)
	// 	{
	// 		servos[i].write(65);
	// 	}
	// 	else
	// 	{
	// 		servos[i].write(37);
	// 	}
	// 	delay(100);
	// }
	if (DEBUG_MODE)
	{

		Serial.println("Done setting motors to G_0");
	}
	delay(2000);

	// Setup lighting
	for (int i = 0; i < NUM_LEDS; i++)
	{
		leds[i] = ColorFromPalette(currentPalette, i, 255, currentBlending);
	}

	// Setup Serial
	xTaskCreatePinnedToCore(
			setupSerial,			 /* Function to implement the task */
			"SerialTask",			 /* Name of the task */
			10000,						 /* Stack size in words */
			NULL,							 /* Task input parameter */
			1,								 /* Priority of the task */
			&SerialTaskHandle, /* Task handle. */
			0);								 /* Core where the task should run */
	// Setup Main Loop
	xTaskCreatePinnedToCore(
			setupMainLoop,		 /* Function to implement the task */
			"MainLoopTask",		 /* Name of the task */
			10000,						 /* Stack size in words */
			NULL,							 /* Task input parameter */
			1,								 /* Priority of the task */
			&OutputTaskHandle, /* Task handle. */
			1);								 /* Core where the task should run */
}

void loop()
{
	// Check for messages on Serial2 and pass them upstream if in Debug
	// if (DEBUG_MODE && Serial2)
	// {
	// 	while (Serial2.available())
	// 	{
	// 		uint8_t data = Serial2.read();
	// 		mainSerial.send(&data, 1);
	// 	}
	// }
}
