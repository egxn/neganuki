import lgpio
import time
import logging

class Stepper28BYJ48:
    """
    28BYJ-48 stepper motor controller using rpi-lgpio.
    Compatible with ULN2003 driver and Raspberry Pi 3B.
    
    Features:
    - Half-step sequence for precision and torque
    - Absolute position tracking
    - Robust error handling
    - Reinitialization after errors
    """

    # Half-step sequence (8 steps)
    HALF_STEP_SEQ = [
        [1,0,0,0],
        [1,1,0,0],
        [0,1,0,0],
        [0,1,1,0],
        [0,0,1,0],
        [0,0,1,1],
        [0,0,0,1],
        [1,0,0,1]
    ]

    # Motor specifications (internal gear ratio 64:1)
    STEPS_PER_REV = 4096
    
    def __init__(self, pins=(17, 18, 27, 22), delay=0.002):
        """
        Initialize stepper motor controller.
        
        :param pins: GPIO pins connected to ULN2003 IN1-IN4
        :param delay: Time between steps in seconds
        """
        self.log = logging.getLogger("Stepper28BYJ48")
        self.pins = pins
        self.delay = delay
        self.handle = None
        self.step_count = len(self.HALF_STEP_SEQ)
        self.current_step = 0
        self.total_steps = 0  # Absolute position tracking
        
        # Initialize GPIO
        self._initialize_gpio()

    def _initialize_gpio(self):
        """Initialize GPIO chip and configure pins."""
        try:
            if self.handle is not None:
                self.log.warning("GPIO already initialized, skipping")
                return
                
            self.log.info("Opening GPIO chip 0")
            self.handle = lgpio.gpiochip_open(0)
            
            # Configure pins as output
            for pin in self.pins:
                lgpio.gpio_claim_output(self.handle, pin)
                lgpio.gpio_write(self.handle, pin, 0)
                
            self.log.info(f"GPIO initialized successfully on pins {self.pins}")
            
        except Exception as e:
            self.log.error(f"Failed to initialize GPIO: {e}")
            self.log.error("Make sure you have permissions (run as root or add user to gpio group)")
            self.log.error("Also verify rpi-lgpio is installed: pip install rpi-lgpio")
            raise RuntimeError(f"GPIO initialization failed: {e}")

    def step(self, steps=1, direction=1):
        """
        Move the motor a number of steps.
        
        :param steps: Number of steps (must be >= 0)
        :param direction: 1 = CW, -1 = CCW
        :return: True if successful, False if failed
        """
        # Parameter validation
        if steps < 0:
            self.log.error(f"Invalid steps value: {steps} (must be >= 0)")
            return False
            
        if direction not in (1, -1):
            self.log.error(f"Invalid direction: {direction} (must be 1 or -1)")
            return False
        
        if self.handle is None:
            self.log.error("GPIO not initialized")
            return False
        
        try:
            for i in range(steps):
                self.current_step = (self.current_step + direction) % self.step_count
                seq = self.HALF_STEP_SEQ[self.current_step]

                for pin, val in zip(self.pins, seq):
                    lgpio.gpio_write(self.handle, pin, val)

                time.sleep(self.delay)
                
                # Update absolute position
                self.total_steps += direction
            
            self.log.debug(f"Moved {steps} steps in direction {direction}, total position: {self.total_steps}")
            return True
            
        except Exception as e:
            self.log.error(f"Step failed: {e}")
            return False

    def rotate_deg(self, degrees, direction=1):
        """
        Rotate the motor by an approximate number of degrees.
        
        :param degrees: Degrees to rotate (can be negative to reverse direction)
        :param direction: 1 = CW, -1 = CCW (multiplied by sign of degrees)
        :return: True if successful, False if failed
        """
        # Allow negative degrees to reverse direction
        if degrees < 0:
            degrees = abs(degrees)
            direction *= -1
        
        steps_to_move = int((degrees / 360.0) * self.STEPS_PER_REV)
        
        if steps_to_move == 0:
            self.log.warning(f"Degrees {degrees} too small, no movement")
            return True
            
        self.log.info(f"Rotating {degrees}° ({steps_to_move} steps) in direction {direction}")
        return self.step(steps=steps_to_move, direction=direction)
    
    def stop(self):
        """
        Stop the motor safely (turn off all coils).
        Useful for emergency stop.
        """
        if self.handle is None:
            self.log.warning("Cannot stop: GPIO not initialized")
            return False
            
        try:
            for pin in self.pins:
                lgpio.gpio_write(self.handle, pin, 0)
            self.log.info("Motor stopped (all coils off)")
            return True
        except Exception as e:
            self.log.error(f"Stop failed: {e}")
            return False
    
    def hold(self):
        """
        Hold current motor position (energize coils at current position).
        Useful for maintaining torque without movement.
        """
        if self.handle is None:
            self.log.warning("Cannot hold: GPIO not initialized")
            return False
            
        try:
            seq = self.HALF_STEP_SEQ[self.current_step]
            for pin, val in zip(self.pins, seq):
                lgpio.gpio_write(self.handle, pin, val)
            self.log.debug("Motor holding position")
            return True
        except Exception as e:
            self.log.error(f"Hold failed: {e}")
            return False
    
    def reset_position(self):
        """Reset absolute position counter to zero."""
        self.total_steps = 0
        self.log.info("Position counter reset to 0")
    
    def get_position(self):
        """
        Get current position in steps from start.
        
        :return: Number of steps (can be negative)
        """
        return self.total_steps
    
    def get_position_degrees(self):
        """
        Get current position in degrees.
        
        :return: Degrees from start
        """
        return (self.total_steps / self.STEPS_PER_REV) * 360.0

    def cleanup(self):
        """
        Turn off pins and safely release GPIO.
        Does not raise exceptions, only logs errors.
        """
        if self.handle is None:
            self.log.warning("GPIO not initialized, nothing to cleanup")
            return
        
        # Turn off all pins first
        for pin in self.pins:
            try:
                lgpio.gpio_write(self.handle, pin, 0)
            except Exception as e:
                self.log.warning(f"Failed to turn off pin {pin}: {e}")
        
        # Free pins individually
        for pin in self.pins:
            try:
                lgpio.gpio_free(self.handle, pin)
            except Exception as e:
                self.log.warning(f"Failed to free pin {pin}: {e}")
        
        # Close chip
        try:
            lgpio.gpiochip_close(self.handle)
            self.handle = None
            self.log.info("Stepper cleaned up successfully")
        except Exception as e:
            self.log.error(f"Failed to close GPIO chip: {e}")
            self.handle = None
    
    def reinitialize(self):
        """
        Reinitialize GPIO after error or cleanup.
        Useful for automatic recovery.
        """
        self.log.info("Reinitializing motor")
        self.cleanup()
        time.sleep(0.5)  # Brief pause to ensure release
        self._initialize_gpio()
        self.log.info("Motor reinitialized successfully")


# Alias for compatibility with PipelineController
StepperMotor = Stepper28BYJ48
