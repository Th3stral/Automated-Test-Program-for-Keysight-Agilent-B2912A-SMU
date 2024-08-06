from numpy import zeros

class WaveGen:
    def __init__(self, magnitude=0, threshold=1):
        """
        Initialize the WaveGen class with a specified magnitude and threshold.

        Parameters:
        magnitude (int): The magnitude, which is 10 to the power of n, default value is 0.
        threshold (float): The threshold value for high/low values, default value is 1.
        """
        self.magnitude = 10 ** magnitude
        self.threshold = threshold

    def _check_safety(self, value):
        """
        Check if the given value exceeds the safety threshold and give specific warning.

        Parameters:
        value (float): The value to be checked.

        Returns:
        bool: True if the value exceeds the threshold, False otherwise.
        """
        scaled_value = value * self.magnitude
        if abs(scaled_value) >= self.threshold:
            return False
        else:
            return True


    def generate_pulse_wave(self, length, pulse_width, pulse_position, high_value=1):
        """
        Generate a pulse wave numpy array.

        Parameters:
        length (int): Length of the array.
        pulse_width (int): Width of the pulse (high value duration).
        pulse_position (int): Start position of the pulse.
        high_value (float): High value of the pulse. Default is 1, scaled by magnitude.

        Returns:
        np.ndarray: A numpy array containing the pulse wave.
        """
        if pulse_position + pulse_width > length:
            raise ValueError("Pulse position and width exceed array length")
        
        # Check safety for high_value
        safe = self._check_safety(high_value)
        
        # Apply magnitude to high_value
        high_value *= self.magnitude
        
        # Initialize array with zeros
        pulse_wave = zeros(length)
        
        # Set the pulse high value
        pulse_wave[pulse_position:pulse_position + pulse_width] = high_value
        
        return pulse_wave

    def generate_square_wave(self, length, high_value=1, low_value=-1, period=10, duty_cycle=0.5, init_time=0):
        """
        Generate a square wave numpy array.

        Parameters:
        length (int): Length of the array.
        high_value (float): High value of the square wave. Default is 1, scaled by magnitude.
        low_value (float): Low value of the square wave. Default is -1, scaled by magnitude.
        period (int): Period of the square wave (total duration of high and low values).
        duty_cycle (float): Duty cycle of the square wave (high value duration as a fraction of the period, range 0 to 1).
        init_time (int): Initial time with value 0 at the beginning of the array.

        Returns:
        np.ndarray: A numpy array containing the square wave.
        """
        # Check safety for high_value and low_value
        hi_safe = self._check_safety(high_value)
        lo_safe = self._check_safety(low_value)
        
        # Apply magnitude to high_value and low_value
        high_value *= self.magnitude
        low_value *= self.magnitude
        
        # Initialize array
        square_wave = zeros(length)
        
        # Calculate high duration
        high_duration = int(period * duty_cycle)
        
        # Generate the square wave starting after the init_time
        i = init_time
        while i < length:
            if i + high_duration <= length:
                square_wave[i:i + high_duration] = high_value
            else:
                square_wave[i:length] = high_value
                break
            i += high_duration
            if i + (period - high_duration) <= length:
                square_wave[i:i + (period - high_duration)] = low_value
            else:
                square_wave[i:length] = low_value
                break
            i += (period - high_duration)
        
        return square_wave