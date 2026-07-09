import logging
from dataclasses import dataclass
from typing import Callable, List, Dict, Type, Any

logger = logging.getLogger("event_bus")

class Event:
    """Base class for all typed pipeline events."""
    pass

@dataclass
class SpeechStarted(Event):
    turn_id: str

@dataclass
class SpeechFinished(Event):
    turn_id: str

@dataclass
class TranscriptReady(Event):
    turn_id: str
    text: str

@dataclass
class ReasoningStarted(Event):
    turn_id: str

@dataclass
class TokenGenerated(Event):
    turn_id: str
    token: str

@dataclass
class ChunkReady(Event):
    turn_id: str
    text: str

@dataclass
class AudioStarted(Event):
    turn_id: str

@dataclass
class AudioChunkEvent(Event):
    turn_id: str
    pcm_bytes: bytes

@dataclass
class AudioFinished(Event):
    turn_id: str

@dataclass
class Interrupted(Event):
    turn_id: str

@dataclass
class Cancelled(Event):
    turn_id: str

@dataclass
class Error(Event):
    turn_id: str
    message: str

class EventBus:
    """
    A simple, lightweight typed event bus supporting synchronous and asynchronous listeners.
    """
    def __init__(self):
        self._listeners: Dict[Type[Event], List[Callable[[Any], Any]]] = {}

    def subscribe(self, event_type: Type[Event], callback: Callable[[Any], Any]):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def publish(self, event: Event):
        event_type = type(event)
        if event_type in self._listeners:
            for listener in self._listeners[event_type]:
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(listener):
                        asyncio.create_task(listener(event))
                    else:
                        listener(event)
                except Exception as e:
                    logger.error(f"Error executing listener for {event_type.__name__}: {e}")
