import logging
import os
from pathlib import Path
import sys
import time

try:
    import RPi.GPIO as GPIO  # type: ignore[import-not-found]
    GPIO_IMPORT_ERROR = None
except Exception as exc:
    GPIO = None
    GPIO_IMPORT_ERROR = exc


class _MockGPIO:
    """Minimal RPi.GPIO-compatible shim for non-Raspberry Pi development."""

    BCM = "BCM"
    OUT = "OUT"
    LOW = 0
    HIGH = 1

    def setwarnings(self, _enabled):
        return None

    def setmode(self, _mode):
        return None

    def setup(self, _pin, _direction, initial=LOW):
        return initial

    def output(self, _pin, _value):
        return None

    def cleanup(self, _pins=None):
        return None


class Stepper28BYJ48:
    """
    28BYJ-48 stepper motor controller using an RPi.GPIO-compatible backend.
    Compatible with ULN2003 driver and Raspberry Pi 3B.

    Features:
    - Half-step sequence for precision and torque
    - Absolute position tracking
    - Robust error handling
    - Reinitialization after errors
    """

    # Half-step sequence (8 steps)
    HALF_STEP_SEQ = [
        [1, 0, 0, 0],
        [1, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 1],
        [0, 0, 0, 1],
        [1, 0, 0, 1],
    ]

    # Motor specifications (internal gear ratio 64:1)
    STEPS_PER_REV = 4096
    _SIMULATION_ENV_VAR = "NEGANUKI_SIMULATE_GPIO"
    _DEVICE_TREE_MODEL_PATHS = (
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    )

    def __init__(self, pins=(17, 18, 27, 22), delay=0.002):
        """
        Initialize stepper motor controller.

        :param pins: GPIO pins connected to ULN2003 IN1-IN4
        :param delay: Time between steps in seconds
        """
        self.log = logging.getLogger("Stepper28BYJ48")
        self.pins = pins
        self.delay = delay
        self.initialized = False
        self.step_count = len(self.HALF_STEP_SEQ)
        self.current_step = 0
        self.total_steps = 0  # Absolute position tracking
        self.simulated = False
        self.is_raspberry_pi = self._detect_raspberry_pi()
        self.gpio = self._resolve_gpio_backend()

        # Initialize GPIO
        self._initialize_gpio()

    def _resolve_gpio_backend(self):
        simulate_gpio = os.getenv(self._SIMULATION_ENV_VAR, "").strip().lower()
        force_simulation = simulate_gpio in {"1", "true", "yes", "on"}

        if force_simulation:
            self.simulated = True
            self.log.warning(
                "Using simulated GPIO because %s is enabled",
                self._SIMULATION_ENV_VAR,
            )
            return _MockGPIO()

        if GPIO is not None:
            return GPIO

        if self.is_raspberry_pi:
            raise RuntimeError(self._build_gpio_install_help())

        self.simulated = True
        self.log.warning(
            "RPi.GPIO is unavailable (%s). Falling back to simulated GPIO backend.",
            GPIO_IMPORT_ERROR,
        )
        self.log.warning(
            "Motor movements will be logged but no physical GPIO pins will be driven."
        )
        self.log.warning(
            "Install Raspberry Pi support with: poetry install --extras \"gpio\""
        )
        return _MockGPIO()

    def _detect_raspberry_pi(self):
        for model_path in self._DEVICE_TREE_MODEL_PATHS:
            try:
                model = model_path.read_text(encoding="utf-8", errors="ignore").strip("\x00 \n")
            except OSError:
                continue

            if "Raspberry Pi" in model:
                return True

        return False

    def _build_gpio_install_help(self):
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        import_error = GPIO_IMPORT_ERROR or "unknown import error"

        return (
            f"RPi.GPIO import failed on Raspberry Pi hardware: {import_error}. "
            "For Raspberry Pi 3B on Debian Trixie, the safest compatible module is "
            "'python3-rpi.gpio' from Debian, which provides the same 'RPi.GPIO' import. "
            "If you prefer 'rpi-lgpio', install its 'lgpio' dependency too and do not "
            "install 'rpi-gpio' and 'rpi-lgpio' in the same Python environment. "
            f"Current Python version: {python_version}. "
            f"Set {self._SIMULATION_ENV_VAR}=1 only if you intentionally want simulated GPIO."
        )

    def _initialize_gpio(self):
        """Initialize GPIO and configure pins."""
        try:
            if self.initialized:
                self.log.warning("GPIO already initialized, skipping")
                return

            self.log.info("Initializing GPIO in BCM mode")
            self.gpio.setwarnings(False)
            self.gpio.setmode(self.gpio.BCM)

            for pin in self.pins:
                self.gpio.setup(pin, self.gpio.OUT, initial=self.gpio.LOW)

            self.initialized = True
            if self.simulated:
                self.log.info("Simulated GPIO initialized on pins %s", self.pins)
            else:
                self.log.info("GPIO initialized successfully on pins %s", self.pins)

        except Exception as e:
            self.log.error(f"Failed to initialize GPIO: {e}")
            self.log.error("Make sure you have permissions (run as root or add user to gpio group)")
            self.log.error('Also verify the Poetry extra is installed: poetry install --extras "gpio"')
            self.log.error("If needed, add it explicitly with: poetry add rpi-lgpio")
            raise RuntimeError(f"GPIO initialization failed: {e}")

    def step(self, steps=1, direction=1):
        """
        Move the motor a number of steps.

        :param steps: Number of steps (must be >= 0)
        :param direction: 1 = CW, -1 = CCW
        :return: True if successful, False if failed
        """
        if steps < 0:
            self.log.error(f"Invalid steps value: {steps} (must be >= 0)")
            return False

        if direction not in (1, -1):
            self.log.error(f"Invalid direction: {direction} (must be 1 or -1)")
            return False

        if not self.initialized:
            self.log.error("GPIO not initialized")
            return False

        try:
            for _ in range(steps):
                self.current_step = (self.current_step + direction) % self.step_count
                seq = self.HALF_STEP_SEQ[self.current_step]

                for pin, val in zip(self.pins, seq):
                    self.gpio.output(pin, self.gpio.HIGH if val else self.gpio.LOW)

                time.sleep(self.delay)
                self.total_steps += direction

            self.log.debug(
                "Moved %s steps in direction %s, total position: %s",
                steps,
                direction,
                self.total_steps,
            )
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
        if not self.initialized:
            self.log.warning("Cannot stop: GPIO not initialized")
            return False

        try:
            for pin in self.pins:
                self.gpio.output(pin, self.gpio.LOW)
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
        if not self.initialized:
            self.log.warning("Cannot hold: GPIO not initialized")
            return False

        try:
            seq = self.HALF_STEP_SEQ[self.current_step]
            for pin, val in zip(self.pins, seq):
                self.gpio.output(pin, self.gpio.HIGH if val else self.gpio.LOW)
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
        if not self.initialized:
            self.log.warning("GPIO not initialized, nothing to cleanup")
            return

        for pin in self.pins:
            try:
                self.gpio.output(pin, self.gpio.LOW)
            except Exception as e:
                self.log.warning(f"Failed to turn off pin {pin}: {e}")

        try:
            self.gpio.cleanup(self.pins)
            self.initialized = False
            self.log.info("Stepper cleaned up successfully")
        except Exception as e:
            self.log.error(f"Failed to cleanup GPIO: {e}")
            self.initialized = False

    def reinitialize(self):
        """
        Reinitialize GPIO after error or cleanup.
        Useful for automatic recovery.
        """
        self.log.info("Reinitializing motor")
        self.cleanup()
        time.sleep(0.5)
        self._initialize_gpio()
        self.log.info("Motor reinitialized successfully")


# Alias for compatibility with PipelineController
StepperMotor = Stepper28BYJ48
