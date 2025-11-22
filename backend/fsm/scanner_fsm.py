import yaml
from pathlib import Path
from transitions import Machine


class ScannerFSM:
    """
    Finite State Machine that controls the film scanning process.
    Loads its structure from states.yml for easy modification.
    """

    def __init__(self, config_path=None, callbacks=None):
        """
        :param config_path: Optional path to the YAML FSM definition.
        :param callbacks: Optional dict of callbacks for state entry actions.
                          Example: {"on_enter_capturing": some_function}
        """
        self.config_path = config_path or Path(__file__).parent / "states.yaml"
        self.callbacks = callbacks or {}

        with open(self.config_path, "r") as f:
            fsm_config = yaml.safe_load(f)

        states = fsm_config.get("states", [])
        transitions = fsm_config.get("transitions", [])
        initial = fsm_config.get("initial", "idle")

        machine = Machine(
            model=self,
            states=states,
            transitions=transitions,
            initial=initial,
            auto_transitions=False,
        )

        # Register and validate callbacks
        for name, func in self.callbacks.items():
            if not callable(func):
                raise ValueError(f"Callback '{name}' must be callable, got {type(func)}")
            if not name.startswith("on_"):
                raise ValueError(f"Callback name '{name}' should start with 'on_' (e.g., 'on_enter_capturing')")
            setattr(self, name, func)

        self.machine = machine

    # -------------------- Condition Methods --------------------
    # These methods are referenced in states.yaml as conditions for transitions

    def is_retry_allowed(self):
        """Check if capture retry is allowed (e.g., max retries not exceeded)."""
        max_retries = getattr(self, 'max_retries', 3)
        current_retries = getattr(self, 'retry_count', 0)
        return current_retries < max_retries

    def is_recoverable(self):
        """Check if error state is recoverable."""
        # Override this method to implement custom recovery logic
        return True

    def is_camera_recoverable(self):
        """Check if camera error can be recovered."""
        # Implement camera-specific recovery checks
        # e.g., check if camera is still connected, try reinitialization
        return True

    def is_motor_recoverable(self):
        """Check if motor error can be recovered."""
        # Implement motor-specific recovery checks
        # e.g., check if motor is responding, try re-homing
        return True

    # -------------------- Helper Methods --------------------

    def reset_retry_count(self):
        """Reset retry counter (call this when entering capturing state)."""
        self.retry_count = 0

    def increment_retry_count(self):
        """Increment retry counter (call this when retrying capture)."""
        self.retry_count = getattr(self, 'retry_count', 0) + 1

    # Optional debugging helper
    def debug_state(self):
        print(f"[FSM] Current state → {self.state}")
