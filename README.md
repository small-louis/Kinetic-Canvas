# Kinetic Canvas

A kinetic sculpture that moves a fabric surface through mechanical linkages driven by servo motors. Gesture input from a Leap Motion controller is classified by Wekinator (machine learning) and mapped to wave patterns via TouchDesigner, which drives the physical surface in real time.

Won the Interplay competition. Built as part of IDE Cyberphysical Systems at Imperial College London / Royal College of Art (2025).

## Architecture

```
Leap Motion  -->  Python (OSC)  -->  Wekinator  -->  TouchDesigner  -->  Python  -->  Arduino  -->  Servos
```

1. **`leap_to_weka/`** — Captures hand tracking data from the Leap Motion and sends it to Wekinator over OSC.
2. **Wekinator** — Classifies gestures and outputs waveform parameters.
3. **TouchDesigner** — Maps gesture parameters to wave patterns for the servo array.
4. **`weka_to_arduino/`** — Receives waveform data, computes motor positions via inverse kinematics, and sends commands to the Arduino over serial.
5. **`arduino/`** — PlatformIO firmware that drives the servo motors.

## Other files

- **`Design_code/`** — Inverse kinematics lookup tables and testing scripts.
- **`TouchDesigner.toe`** — TouchDesigner project file for the wave mapping.
- **`Main Schematic.fzz`** — Fritzing wiring schematic.

## Setup

1. Install Python 3.13
2. `pip install -r requirements.txt`

## Running

```bash
python -m weka_to_arduino.main
```

## More

Project page: [louisbrouwer.com/kinetic-canvas.html](https://louisbrouwer.com/kinetic-canvas.html)
