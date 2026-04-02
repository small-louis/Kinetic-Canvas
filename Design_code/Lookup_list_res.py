import numpy as np

# Constants for the equation (replace with actual values)
a = 19  # Example value
c = 38  # Example value
ratio = 3  # Ratio of the connecting rod to tip motion
units = "mm"
b_0 = np.sqrt(c**2 - a**2)  # the original distance between servo and stick
print("the b_0 value is: ", b_0)

# Define the range of g in degrees with 1-degree increments
g_degrees = np.arange(35, 150, 1)  

# Initialize an array to store the corresponding x values
x_lookup = np.zeros_like(g_degrees, dtype=float)

# Calculate x for each g in the range
for i, g in enumerate(g_degrees):
    g_rad = np.radians(g)  # Convert g to radians for computation
    # Compute x using the rearranged equation
    x_value = ratio * ((c * np.sin((np.pi) - g_rad - np.arcsin(np.sin(g_rad)*(a / c))) / np.sin(g_rad)) - b_0)
    #x_value = (c * np.sin((np.pi) - g_rad - np.arcsin(np.sin(g_rad)*(a / c))) / np.sin(g_rad))
    x_lookup[i] = np.round(x_value, 2)  # Round to 2 decimal places

# Calculate the differences between consecutive x values
x_differences = np.abs(np.diff(x_lookup))

# Find the maximum difference
max_difference = np.max(x_differences)
max_difference_round = np.round(max_difference, 2)
max_index = np.argmax(x_differences)

# Output the lookup table
print("Angle (degrees) | x ({}):".format(units))
for g, x in zip(g_degrees, x_lookup):
    print(f"{g}° : {x} {units}")

# Output the largest difference
print("\nLargest difference between consecutive x values:", max_difference_round, units)
print("Occurs between angles:", g_degrees[max_index], "and", g_degrees[max_index + 1])

# Function to look up a specific x value and find the corresponding angle
def lookup_angle(x_target):
    # Find the closest match or interpolate if needed
    if x_target in x_lookup:
        angle = g_degrees[np.where(x_lookup == x_target)[0][0]]
        print(f"The angle corresponding to x = {x_target} {units} is approximately {angle}°.")
    else:
        # Interpolation for values not exactly in x_lookup
        idx = np.searchsorted(x_lookup, x_target)
        if idx == 0 or idx == len(x_lookup):
            print("The target x value is out of range.")
        else:
            # Linear interpolation between two closest points
            x1, x2 = x_lookup[idx - 1], x_lookup[idx]
            g1, g2 = g_degrees[idx - 1], g_degrees[idx]
            angle = g1 + (x_target - x1) * (g2 - g1) / (x2 - x1)
            print(f"The interpolated angle corresponding to x = {x_target} {units} is approximately {np.round(angle, 2)}°.")


# Function to calculate and print the difference between the largest and smallest x values
def print_x_range_difference():
    x_min = np.min(x_lookup)
    x_max = np.max(x_lookup)
    difference = x_max - x_min
    print(f"The difference between the largest and smallest x values is {difference} {units}.")

# Example usage of lookup function
print(lookup_angle(50))  # Replace 50 with any x value you want to look up

# Print the difference between the largest and smallest x values
print_x_range_difference()


