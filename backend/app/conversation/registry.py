from dataclasses import dataclass, field
from typing import Dict, Type, Any, Set, Optional
from .interfaces import ISpeechToSpeechModel

@dataclass
class InferenceInfo:
    """
    Metadata info and capabilities for a registered model implementation.
    """
    id: str
    version: str
    modality: str
    implementation: Type[Any]
    runtime: str
    capabilities: Set[str] = field(default_factory=set)

    def supports(self, capability: str) -> bool:
        """Returns True if the model supports the specified capability."""
        return capability in self.capabilities

class InferenceRegistry:
    """
    Registry managing capability indexing and model implementation discovery.
    """
    _registry: Dict[str, InferenceInfo] = {}

    @classmethod
    def register(
        cls, 
        id: str, 
        version: str, 
        modality: str, 
        implementation: Type[Any], 
        runtime: str, 
        capabilities: Set[str]
    ):
        """Registers a new model runtime configuration."""
        info = InferenceInfo(
            id=id,
            version=version,
            modality=modality,
            implementation=implementation,
            runtime=runtime,
            capabilities=capabilities
        )
        cls._registry[id] = info
        
    @classmethod
    def get_info(cls, model_id: str) -> Optional[InferenceInfo]:
        """Retrieves capabilities metadata for a model ID."""
        return cls._registry.get(model_id)

    @classmethod
    def get_model(cls, model_id: str, **kwargs) -> Any:
        """Instantiates the model driver registered for the specified ID."""
        info = cls.get_info(model_id)
        if not info:
            raise ValueError(f"Unknown inference model: {model_id}")
        return info.implementation(**kwargs)
