import asyncio
from functools import partial
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, RadioButtons, Button
from matplotlib.animation import FuncAnimation
from typing import TYPE_CHECKING, List
from openmeteopy.client import OpenMeteo
from openmeteopy.hourly import HourlyMarine
from openmeteopy.options import MarineOptions
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# import requests_cache
from retry_requests import retry

if TYPE_CHECKING:
    from .main import AnimationManager


class IK_LookupTable:
    """Class to handle the calculation of lookup arrays"""

    def __init__(self, a, c, ratio, g_0):
        self.a = a
        self.c = c
        self.ratio = ratio
        self.g_0 = g_0 * np.pi / 180
        self.g_degrees = np.arange(
            1, 200, 1
        )  # this range can be set depending on what is observed in the CAD simulation
        # This lookup table is indexed by angle and returns mm offset
        self.lookup_array = self.calculate_lookup()
        # This lookup table is indexed by mm offset and returns angle

    def calculate_lookup(self):
        b_0 = (
            self.c
            * np.sin(
                (np.pi) - self.g_0 - np.arcsin(np.sin(self.g_0) * (self.a / self.c))
            )
            / np.sin(self.g_0)
        )  # the original distance between servo and stick
        x_lookup = np.zeros_like(self.g_degrees, dtype=float)

        for i, g in enumerate(self.g_degrees):
            g_rad = np.radians(g)  # Convert g to radians for computation
            # Compute x using the rearranged equation
            x_value = self.ratio * (
                (
                    self.c
                    * np.sin(
                        (np.pi) - g_rad - np.arcsin(np.sin(g_rad) * (self.a / self.c))
                    )
                    / np.sin(g_rad)
                )
                - b_0
            )
            x_lookup[i] = np.round(x_value, 2)  # Round to 2 decimal places

        stack_array = np.column_stack((self.g_degrees, x_lookup))
        return stack_array

    def print_x_range_difference(self):
        x_min = np.min(self.lookup_array)
        x_max = np.max(self.lookup_array)
        difference = x_max - x_min
        print(
            f"The difference between the largest and smallest x values is {difference} mm."
        )

    def lookup_angle(self, y_position):
        # Find the closest x value in the lookup array and return its corresponding angle
        closest_idx = (np.abs(self.lookup_array[:, 1] - y_position)).argmin()
        return self.lookup_array[closest_idx, 0]  # Return the angle


params_top = {"a": 19, "c": 37.5, "ratio": 300 / 132, "g_0": 70}
params_bottom = {"a": 20, "c": 38, "ratio": 300 / 97, "g_0": 61}

lookup_table_top = IK_LookupTable(**params_top)
lookup_table_bottom = IK_LookupTable(**params_bottom)


class Wave:
    """Basic wave class that represents the function of a single wave"""

    t = 0

    def __init__(self, amplitude: float, period: float, direction: int, x_scale=200):
        self.amplitude = amplitude
        self.period = period
        self.direction = direction
        self.g = 9.81
        self.x_scale = x_scale
        self.wave_space = np.zeros(x_scale)

    def wavelength(self):
        return self.g * self.period**2 / (2 * np.pi)

    def speed(self):
        return (self.wavelength() / self.period) / 1

    def calculate_wave(self, x, t):
        lmbda = self.wavelength()
        v = self.speed()
        return self.amplitude * np.sin(
            ((2 * np.pi) / lmbda) * (x - self.direction * v * t)
        )

    def tick(self, time_step=0.1, n_samples=1000):
        self.wave_space = np.roll(self.wave_space, self.direction)
        new_wavepoint = self.calculate_wave(0, self.t)
        if self.direction == 1:
            self.wave_space[0] = new_wavepoint
        else:
            self.wave_space[-1] = new_wavepoint
        self.t += time_step
        # Return n_samples of the wave space, with linear interpolation
        return self.get_wave_space(n_samples)

    def get_wave_space(self, n_samples=None):
        if n_samples is None:
            return self.wave_space
        return np.interp(
            np.linspace(0, self.x_scale, n_samples),
            np.arange(self.x_scale),
            self.wave_space,
        )

    def sample_at_time(self, num_samples, t):
        x = np.linspace(0, 80, num_samples)
        return self.calculate_wave(x, t)


class WaveSimulation:
    """Wave simulation class that handles the display and animation of multiple waves. Useful for visualizing the superposition of waves and debugging."""

    fig = None
    waves: List[Wave] = []
    # gM_0 = [65, 25, 65, 30, 60, 37, 65]
    gM_0 = [
        60,
        48,
        62,
        45,
        80,
        30,
        90,
        55,
        75,
        37,
        75,
        30,
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
    # Maximum offset in mm
    max_offset = 38

    def __init__(
        self,
        manager: "AnimationManager",
        display_length=40,
        scale=10,
        num_samples=1000,
        time_step=0.05,
    ):
        # Reference to the AnimationManager instance
        self.manager = manager
        # Key parameters for display and wave physics
        self.display_length = display_length
        self.servo_count = self.manager.num_motors
        self.scale = scale
        self.num_samples = num_samples
        self.time_step = time_step
        self.x = np.linspace(0, display_length * scale, self.num_samples)
        self.t = 0
        self.waves = [
            Wave(1.0, 12, 1),
            Wave(0, 12, 1),
            Wave(0, 12, 1),
            Wave(0, 12, 1),
        ]
        self.set_from_reality()
        self.combined_history = [0] * self.num_samples
        self.mode = "Continuous"
        self.servo_x_positions = np.linspace(
            0, display_length * scale, self.servo_count
        )

    def set_from_reality(self, lat=35.535085, lon=140.44020):
        """Fetch real-world wave data and set wave parameters."""
        hourly = (
            HourlyMarine()
            .wave_height()
            .wave_period()
            .wave_direction()
            .swell_wave_height()
            .swell_wave_period()
            .swell_wave_direction()
            .wind_wave_height()
            .wind_wave_period()
            .wind_wave_direction()
        )
        options = MarineOptions(lat, lon, forecast_days=1)

        mgr = OpenMeteo(options, hourly)

        # Download data
        meteo = mgr.get_dict()
        hourly_data = meteo["hourly"]

        # Extract data including directions
        wave_main = [
            hourly_data["wave_height"][0],
            hourly_data["wave_period"][0],
            hourly_data["wave_direction"][0],
        ]
        wave_swell = [
            hourly_data["swell_wave_height"][0],
            hourly_data["swell_wave_period"][0],
            hourly_data["swell_wave_direction"][0],
        ]
        wave_wind = [
            hourly_data["wind_wave_height"][0],
            hourly_data["wind_wave_period"][0],
            hourly_data["wind_wave_direction"][0],
        ]

        print("Current forecast:")
        print(
            f"Main wave: Height={wave_main[0]}, Period={wave_main[1]}, Direction={wave_main[2]}°"
        )
        print(
            f"Swell wave: Height={wave_swell[0]}, Period={wave_swell[1]}, Direction={wave_swell[2]}°"
        )
        print(
            f"Wind wave: Height={wave_wind[0]}, Period={wave_wind[1]}, Direction={wave_wind[2]}°"
        )

        # Function to convert meteorological direction to wave movement direction
        def get_wave_movement_direction(wave_direction):
            if wave_direction is None:
                return 1
            # Convert to wave movement direction (direction waves are heading to)
            wave_moving_direction = (wave_direction + 180) % 360
            # Determine simulation direction: +1 for right, -1 for left
            if 0 <= wave_moving_direction < 180:
                return 1  # Waves moving to the right
            else:
                return -1  # Waves moving to the left

        # Get simulation directions
        wave_main_sim_direction = get_wave_movement_direction(wave_main[2])
        wave_swell_sim_direction = get_wave_movement_direction(wave_swell[2])
        wave_wind_sim_direction = get_wave_movement_direction(wave_wind[2])

        # Set waves [1,2,3] to the main, swell, and wind waves with directions
        if self.waves[1].amplitude is not None:
            self.waves[1].amplitude = wave_main[0] * 3
            self.waves[1].period = wave_main[1] * 5
            self.waves[1].direction = wave_main_sim_direction

        if wave_swell[0] is not None:
            self.waves[2].amplitude = wave_swell[0] * 5
            self.waves[2].period = wave_swell[1] * 5
            self.waves[2].direction = wave_swell_sim_direction

        if wave_wind[0] is not None:
            self.waves[3].amplitude = wave_wind[0] * 8
            self.waves[3].period = wave_wind[1] * 5
            self.waves[3].direction = wave_wind_sim_direction

        # Plot the location on a world map
        self.plot_location_on_map(lat, lon)

        return (wave_main, wave_swell, wave_wind) * 10

    def plot_location_on_map(self, lat, lon):
        """Plot the given latitude and longitude on a world map."""
        # Create a new figure with a specific size
        plt.figure(figsize=(10, 5))

        # Create a GeoAxes object with the Plate Carree projection
        ax = plt.axes(projection=ccrs.PlateCarree())

        # Add land and ocean features
        ax.add_feature(cfeature.LAND)
        ax.add_feature(cfeature.OCEAN)
        ax.add_feature(cfeature.COASTLINE)
        ax.add_feature(cfeature.BORDERS, linestyle=":")

        # Set extent to show the whole world
        ax.set_global()

        # Plot the location
        ax.plot(lon, lat, "ro", markersize=10, transform=ccrs.Geodetic())

        # Add a title
        ax.set_title("Location of Wave Data")

        # Show the plot
        plt.show()

    def add_wave(self, amplitude, period, direction):
        self.waves.append(Wave(amplitude, period, direction))
        if self.fig:
            self.setup_plot()

    def combined_wave(self, num_samples=None):
        num_samples = num_samples if num_samples is not None else self.num_samples
        # x = x if x is not None else self.x
        # t = t if t is not None else self.t
        # return sum(wave.calculate_wave(x, t) for wave in self.waves)
        return sum(wave.get_wave_space(num_samples) for wave in self.waves)

    def update(self, val):
        for i, (amp_slider, T_slider) in enumerate(self.sliders):
            self.waves[i].amplitude = amp_slider.val
            self.waves[i].period = T_slider.val

        for i, line in enumerate(self.lines):
            line.set_ydata(self.waves[i].get_wave_space(self.x.size))

        self.line_sum.set_ydata(self.combined_wave())
        self.fig.canvas.draw_idle()

    def update_direction(self, label, idx):
        self.waves[idx].direction = 1 if label == "Right" else -1
        self.update(None)

    def update_dots(self):
        if self.mode == "Dots":
            servo_y_positions = [
                sum(wave.calculate_wave(pos, self.t) for wave in self.waves)
                for pos in self.servo_x_positions
            ]
            self.dots.set_ydata(servo_y_positions)

    def toggle_mode(self, label):
        self.mode = label
        show_continuous = self.mode == "Continuous"
        for line in self.lines:
            line.set_visible(show_continuous)
        self.line_sum.set_visible(show_continuous)
        self.dots.set_visible(not show_continuous)
        self.update(None)

    def tick(self, delta=1, update=True):
        """Update the wave simulation by a single time step, optionally specifying the number of time steps to update."""
        step = self.time_step * delta * 50
        self.t += step  # Runs at 50fps in original code
        # Step waves
        for wave in self.waves:
            wave.tick(step, self.num_samples)
        # Update Lines
        for i, line in enumerate(self.lines):
            line.set_ydata(self.waves[i].get_wave_space(self.x.size))
        self.line_sum.set_ydata(self.combined_wave())
        self.update_dots()

        if update:
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
        return self.lines + [self.line_sum]

    def animate(self, i):
        # Helper function for matplotlib FuncAnimation
        return self.tick(1 / 50, False)

    def calculate_discrete_positions(self, count):
        servo_x_positions = np.linspace(0, self.display_length * self.scale, count)
        servo_y_positions = self.combined_wave(servo_x_positions.size)
        return servo_x_positions, servo_y_positions

    def lookup_angle(self, y_position, lookup_table):
        # Finds the angle for a given distance in the lookup table
        closest_idx = (np.abs(lookup_table[:, 1] - y_position)).argmin()
        return lookup_table[closest_idx, 0]  # Return angle

    def calculate_servo_angles(self) -> List[float]:

        # gM_0T = 65
        # GM_0B = 37
        g_0 = [
            params_top["g_0"] if i % 2 == 0 else params_bottom["g_0"]
            for i in range(self.manager.num_motors)
        ]
        # gM_0 = [gM_0T if i % 2 == 0 else GM_0B for i in range(num_servos)]

        # Calculate initial servo_y_positions (without scaling or clipping)
        _, servo_y_positions = self.calculate_discrete_positions(self.servo_count)

        # Scale servo_y_positions to match the range of distances in the lookup tables
        scaled_servo_y_positions = [
            np.clip((y / 12) * self.max_offset, self.max_offset * -1, self.max_offset)
            for y in servo_y_positions
        ]

        # Lookup the corresponding angles for each scaled servo_y_position
        servo_angles_cad = [
            self.lookup_angle(
                y,
                (
                    lookup_table_top.lookup_array
                    if i % 2 == 0
                    else lookup_table_bottom.lookup_array
                ),
            )
            for i, y in enumerate(scaled_servo_y_positions)
        ]

        # Map CAD servo angles to actual servo angles
        servo_angles = [
            self.gM_0[i] + (g_0[i] - servo_angle_cad)
            for i, servo_angle_cad in enumerate(servo_angles_cad)
        ]

        return servo_angles

    async def setup_plot(self):
        if self.fig:
            # Close the previous plot if it exists
            plt.close(self.fig)
        self.fig, self.ax = plt.subplots()
        # Adjust the plot to make room for sliders
        plt.subplots_adjust(left=0.1, bottom=0.35, right=0.9, top=0.9)
        # Set the y-axis limits (magic numbers)
        self.ax.set_ylim([-12, 12])
        self.ax.set_title("Wave Simulation")
        self.ax.set_xlabel("Distance (m)")
        self.ax.set_ylabel("Amplitude (m)")
        self.ax.grid(True)

        # Plot lines for each individual wave and the summed wave
        self.lines = [
            self.ax.plot(
                self.x, wave.calculate_wave(self.x, self.t), lw=2, label=f"Wave {i+1}"
            )[0]
            for i, wave in enumerate(self.waves)
        ]
        self.line_sum = self.ax.plot(
            self.x, self.combined_wave(), lw=2, label="Summed Wave", color="black"
        )[0]
        (self.dots,) = self.ax.plot(
            self.servo_x_positions,
            [0] * self.servo_count,
            "o",
            color="black",
            visible=False,
        )
        self.ax.legend(loc="upper right")

        # Add sliders for amplitude and period for three waves
        axcolor = "lightgoldenrodyellow"
        self.sliders = []
        for i, wave in enumerate(self.waves):
            ax_amp = plt.axes([0.1, 0.25 - i * 0.1, 0.35, 0.03], facecolor=axcolor)
            ax_T = plt.axes([0.1, 0.2 - i * 0.1, 0.35, 0.03], facecolor=axcolor)
            amp_slider = Slider(
                ax_amp, f"Amplitude {i+1}", 0.1, 10.0, valinit=wave.amplitude
            )
            T_slider = Slider(ax_T, f"Period {i+1}", 4.0, 30.0, valinit=wave.period)
            amp_slider.on_changed(self.update)
            T_slider.on_changed(self.update)
            self.sliders.append((amp_slider, T_slider))

        # self.radio_buttons = []
        # for i in range(3):
        #     rax = plt.axes([0.55 + i * 0.15, 0.1, 0.1, 0.1], facecolor=axcolor)
        #     radio = RadioButtons(rax, ("Right", "Left"), active=0)
        #     radio.on_clicked(lambda label, idx=i: self.update_direction(label, idx))
        #     self.radio_buttons.append(radio)
        rax = plt.axes([0.8, 0.05, 0.15, 0.15], facecolor=axcolor)
        self.mode_radio = RadioButtons(rax, ("Continuous", "Dots"))
        self.mode_radio.on_clicked(self.toggle_mode)

        # We could set up the animation here, but instead we will let async ticks take care of this.
        # FuncAnimation(self.fig, self.tick, interval=50)
        self.fig.canvas.draw()
        plt.show(block=False)


if __name__ == "__main__":
    waveSim = WaveSimulation()
    print("Setting up plot...")
    asyncio.run(waveSim.setup_plot())
    print("Running animation...")
    ani = FuncAnimation(waveSim.fig, waveSim.animate, interval=50)
    plt.show()
