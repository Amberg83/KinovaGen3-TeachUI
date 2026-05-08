import threading
import logging

logger = logging.getLogger("EventBus")

class EventBus:
    """
    A lightweight, thread-safe, centralized publisher-subscriber event bus.
    Enables loose coupling between Models, Views, Controllers, and utility systems.
    """
    _listeners = {}
    _lock = threading.RLock() # Thread-safe Reentrant Lock

    @classmethod
    def subscribe(cls, event_name: str, callback):
        """Subscribes a listener callback to a specific event topic."""
        with cls._lock:
            if event_name not in cls._listeners:
                cls._listeners[event_name] = []
            if callback not in cls._listeners[event_name]:
                cls._listeners[event_name].append(callback)
                logger.debug(f"Subscribed listener to event: {event_name}")

    @classmethod
    def unsubscribe(cls, event_name: str, callback):
        """Unsubscribes a listener callback from a specific event topic."""
        with cls._lock:
            if event_name in cls._listeners:
                if callback in cls._listeners[event_name]:
                    cls._listeners[event_name].remove(callback)
                    logger.debug(f"Unsubscribed listener from event: {event_name}")
                if not cls._listeners[event_name]:
                    del cls._listeners[event_name]

    @classmethod
    def publish(cls, event_name: str, *args, **kwargs):
        """Broadcasts an event with optional arguments to all subscribed listeners."""
        # Acquire a shallow copy of listeners list under lock to minimize lock-holding time
        with cls._lock:
            listeners_copy = list(cls._listeners.get(event_name, []))

        if listeners_copy:
            logger.debug(f"Publishing event: {event_name} (args={args}, kwargs={kwargs})")
            for callback in listeners_copy:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in subscriber callback for event '{event_name}': {e}", exc_info=True)
