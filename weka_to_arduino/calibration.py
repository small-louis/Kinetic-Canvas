# motor_calibration.py
from .serial import SerialManager
from .wave import params_bottom, params_top

# Number of servos
num_servos = 21

# Initialize servo positions based on parameters
gM_0T = 65
GM_0B = 37

# g_0_init = [
#     params_top["g_0"] if i % 2 == 0 else params_bottom["g_0"] for i in range(num_servos)
# ]
# gM_0_init = [gM_0T if i % 2 == 0 else GM_0B for i in range(num_servos)]



gM_0_init = [
    65,
    55,
    70,
    45,
    80,
    30,
    90,
    55,
    75,
    37,
    70,
    32,
    75,
    32,
    70,
    35,
    60,
    30,
    70,
    30,
    80,
]
# [67, 55, 85, 45, 95, 30, 95, 61, 77, 45,

# Set up serial connection
serial = SerialManager(None, 115200)


def calibrate_servo():
    """
    Continuously prompt the user to input servo index and angle,
    update the servo position, and modify the gM_0_init list.
    """

    # Start by setting all servos to the existing G_0 values
    for i in range(num_servos):
        serial.set_motor(i, gM_0_init[i], log=True, instant=True)

    print("Servo Motor Calibration Tool")
    print("Type 'exit' to quit.")

    while True:
        try:
            # Prompt user for servo index
            servo_index = input(
                "Enter the servo index (0 to {}): ".format(num_servos - 1)
            )
            if servo_index.lower() == "exit":
                break
            servo_index = int(servo_index)

            # Validate servo index
            if servo_index < 0 or servo_index >= num_servos:
                print(
                    "Invalid servo index. Please enter a value between 0 and {}.".format(
                        num_servos - 1
                    )
                )

                continue

            # Prompt user for angle
            servo_angle = input("Enter the servo angle (0 to 180): ")
            if servo_angle.lower() == "exit":
                break
            servo_angle = int(servo_angle)

            # Validate angle
            if servo_angle < 0 or servo_angle > 180:
                print("Invalid angle. Please enter a value between 0 and 180.")
                continue

            # Update the servo motor
            serial.set_motor(servo_index, servo_angle, log=True, instant=True)
            print(f"Set motor {servo_index} to angle {servo_angle}")

            # Update the gM_0_init list
            gM_0_init[servo_index] = servo_angle
            print(f"Updated gM_0_init[{servo_index}] to {servo_angle}")

        except ValueError:
            print(
                "Invalid input. Please enter numeric values for the servo index and angle."
            )

    print("Exiting Servo Motor Calibration Tool.")
    print(gM_0_init)


if __name__ == "__main__":
    calibrate_servo()
