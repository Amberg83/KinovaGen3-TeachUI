import logging
from .event_bus import EventBus
from .sound_manager import play_chime

logger = logging.getLogger("SoundCoordinator")

class SoundCoordinator:
    """
    Centralizes and coordinates all audio feedback for the TeachUI system.
    Subscribes to standard EventBus notifications and dispatches them to play_chime.
    This keeps robot hardware driver loops and UI controllers completely decoupled from audio playing code.
    """
    def __init__(self):
        self.enabled = True # Simple global mute guard
        self._register_subscribers()
        logger.info("SoundCoordinator initialized and subscribers registered.")

    def _register_subscribers(self):
        """Maps EventBus notifications to corresponding sound manager chimes."""
        
        # --- Hardware Connection Events ---
        EventBus.subscribe("robot_connected", lambda: self._play("connected"))
        EventBus.subscribe("robot_disconnected", lambda block=False: self._play("disconnected", block=block))
        
        # --- Robot Safety and Fault Events ---
        EventBus.subscribe("fault", lambda: self._play("fault"))
        EventBus.subscribe("fault_cleared", lambda: self._play("fault_cleared"))
        EventBus.subscribe("estop", lambda: self._play("estop"))
        
        # --- Admittance Mode Toggle Events ---
        EventBus.subscribe("admittance_enabled", lambda: self._play("admittance_enable"))
        EventBus.subscribe("admittance_disabled", lambda: self._play("admittance_disable"))
        
        # --- Editing and History Events ---
        EventBus.subscribe("waypoint_saved", lambda: self._play("waypoint_saved"))
        EventBus.subscribe("waypoint_deleted", lambda: self._play("delete"))
        EventBus.subscribe("edit_undone", lambda: self._play("undo"))
        EventBus.subscribe("edit_redone", lambda: self._play("redo"))
        
        # --- Waypoint Timeline Order Events ---
        EventBus.subscribe("waypoint_moved_up", lambda: self._play("move_up"))
        EventBus.subscribe("waypoint_moved_down", lambda: self._play("move_down"))
        EventBus.subscribe("waypoint_moved_entry", lambda: self._play("move_entry"))
        
        # --- UI Capture & Replay events ---
        EventBus.subscribe("waypoint_captured", lambda: self._play("captured"))
        EventBus.subscribe("replay_started", lambda: self._play("replay_start"))
        EventBus.subscribe("replay_finished", lambda: self._play("replay_finished"))
        
        # --- Interactive Task and Study Milestones ---
        EventBus.subscribe("task_completed", lambda: self._play("task_completed"))

    def _play(self, chime_name: str, block: bool = False):
        """Plays the designated chime file if the sound is globally enabled."""
        if self.enabled:
            try:
                play_chime(chime_name, block=block)
            except Exception as e:
                logger.error(f"Error playing coordinated chime '{chime_name}': {e}")
