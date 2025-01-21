from abc import ABC, abstractmethod
import sys
from typing import Any

class JsonObject(ABC):
    @abstractmethod
    def to_object(self) -> Any:
        pass

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def fail(msg):
    eprint(f"Error: {msg}")
    exit(1)

def warning(msg):
    eprint(f"Warning: {msg}")
