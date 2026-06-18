from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar


TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


@dataclass
class EngineContext:
    """Shared context passed through the engine pipeline."""
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class AbstractEngine(ABC, Generic[TInput, TOutput]):
    """Base class for all processing engines in the pipeline."""

    def __init__(self, name: str, context: EngineContext | None = None):
        self.name = name
        self.context = context or EngineContext()

    @abstractmethod
    async def process(self, data: TInput) -> TOutput:
        """Process input data and return transformed output.
        
        Args:
            data: Input data of type TInput
            
        Returns:
            Processed output of type TOutput
        """
        ...

    @abstractmethod
    async def validate(self, data: TInput) -> bool:
        """Validate whether the input can be processed.
        
        Args:
            data: Input data to validate
            
        Returns:
            True if input is valid and can be processed
        """
        ...

    async def __call__(self, data: TInput) -> TOutput:
        """Convenience: call the engine directly."""
        if not await self.validate(data):
            raise ValueError(f"Engine {self.name}: input validation failed")
        return await self.process(data)

    def __repr__(self) -> str:
        return f"AbstractEngine(name={self.name!r})"
