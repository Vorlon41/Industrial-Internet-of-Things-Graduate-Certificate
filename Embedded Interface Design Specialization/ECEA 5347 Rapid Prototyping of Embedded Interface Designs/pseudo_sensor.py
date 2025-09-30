# pseudo_sensor.py
import random

class PseudoSensor:
    # Humidity bands 0–100%
    h_range = [0, 20, 20, 40, 40, 60, 60, 80, 80, 90, 70, 50, 30, 10, 0]
    # Temperature bands in FAHRENHEIT (−20 to 100)
    t_range = [-20, -10, 0, 10, 30, 50, 70, 85, 95, 100, 90, 70, 50, 30, 10]

    def __init__(self):
        self.h_index = 0
        self.t_index = 0
        self.hum_val = self.h_range[self.h_index]
        self.temp_val = self.t_range[self.t_index]

    def generate_values(self):
        # Add some jitter within the current band
        self.hum_val = self.h_range[self.h_index] + random.uniform(0, 10)
        self.temp_val = self.t_range[self.t_index] + random.uniform(0, 5)

        # Roll indices
        self.h_index = (self.h_index + 1) % len(self.h_range)
        self.t_index = (self.t_index + 1) % len(self.t_range)

        # Clamp to assignment ranges
        h = max(0.0, min(self.hum_val, 100.0))
        t = max(-20.0, min(self.temp_val, 100.0))
        return h, t

