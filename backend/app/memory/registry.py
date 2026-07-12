from typing import Dict, Any
from app.memory.providers.structured_memory import StructuredMemoryProvider

class MemoryProviderRegistry:
    """
    MemoryProviderRegistry manages available memory providers and instances.
    """
    def __init__(self):
        self._providers: Dict[str, Any] = {}
        # Pre-register default provider
        self.register_provider("structured_memory", StructuredMemoryProvider())

    def register_provider(self, name: str, provider: Any):
        self._providers[name] = provider

    def get_provider(self, name: str = "structured_memory") -> Any:
        provider = self._providers.get(name)
        if not provider:
            raise KeyError(f"Memory provider '{name}' is not registered.")
        return provider

# Global Registry instance
provider_registry = MemoryProviderRegistry()
