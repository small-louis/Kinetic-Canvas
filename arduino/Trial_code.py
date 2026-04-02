import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# Define the points
points = [(0, 0), (0.33, 2), (0.66, 10), (1, 50)]
x_points, y_points = zip(*points)

# Define the exponential function
def exponential(x, a, b):
    return a * np.exp(b * x)

# Fit the exponential function to the points
params, _ = curve_fit(exponential, x_points, y_points, p0=(1, 1))
a, b = params

# Print the final equation
print(f"The final equation is: y = {a:.4f} * e^({b:.4f} * x)")

# Generate x values
x_values = np.linspace(0, 1, 400)
# Generate y values using the exponential function
y_values = exponential(x_values, a, b)

# Plot the results
plt.plot(x_values, y_values, label='Exponential Fit')
plt.scatter(x_points, y_points, color='red', label='Data Points')
plt.xlabel('Distance (m)')
plt.ylabel('Percentage')
plt.legend()
plt.title('Exponential Equation Mapping')
plt.grid(True)
plt.show()