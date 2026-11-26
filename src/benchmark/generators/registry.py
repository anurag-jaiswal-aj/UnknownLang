"""Generator registry for M2.5 task generators."""

from __future__ import annotations

from typing import Any, Callable

from .generator import TaskGenerator, create_generator


class GeneratorRegistry:
    """Registry for task generators with versioning."""
    
    def __init__(self) -> None:
        self._generators: dict[str, dict[str, Callable[..., TaskGenerator]]] = {}
        self._default_version: dict[str, str] = {}
    
    def register(
        self,
        generator_family: str,
        version: str,
        generator_factory: Callable[..., TaskGenerator],
        *,
        default: bool = False,
    ) -> None:
        """Register a task generator factory.
        
        Args:
            generator_family: Generator family identifier (e.g., "answer")
            version: Generator version string
            generator_factory: Factory function that creates a generator
            default: If True, sets this as the default version for the family
        """
        if generator_family not in self._generators:
            self._generators[generator_family] = {}
        
        self._generators[generator_family][version] = generator_factory
        
        if default or generator_family not in self._default_version:
            self._default_version[generator_family] = version
    
    def get(
        self,
        generator_family: str,
        version: str | None = None,
    ) -> Callable[..., TaskGenerator]:
        """Get a registered generator factory.
        
        Args:
            generator_family: Generator family identifier
            version: Version to get (uses default if None)
            
        Returns:
            Generator factory function for the requested version
            
        Raises:
            ValueError: If generator family or version not found
        """
        if generator_family not in self._generators:
            raise ValueError(f"Unknown generator family: {generator_family}")
        
        if version is None:
            version = self._default_version[generator_family]
        
        if version not in self._generators[generator_family]:
            available = sorted(self._generators[generator_family].keys())
            raise ValueError(
                f"Generator {generator_family} version {version} not found. "
                f"Available versions: {available}"
            )
        
        return self._generators[generator_family][version]
    
    def get_all_versions(self, generator_family: str) -> list[str]:
        """Get all available versions for a generator family."""
        if generator_family not in self._generators:
            return []
        return sorted(self._generators[generator_family].keys())
    
    def get_default_version(self, generator_family: str) -> str:
        """Get the default version for a generator family."""
        if generator_family not in self._default_version:
            raise ValueError(f"No default version for generator: {generator_family}")
        return self._default_version[generator_family]


# Global generator registry
_registry = GeneratorRegistry()


def get_registry() -> GeneratorRegistry:
    """Get the global generator registry."""
    return _registry


def _initialize_registry() -> None:
    """Initialize the generator registry with default generators."""
    # Register default answer task generator
    _registry.register(
        generator_family="answer",
        version="1.0.0",
        generator_factory=create_generator,
        default=True,
    )


def get_generator(
    environment_id: str,
    derivation_seed: str,
    generator_family: str = "answer",
    version: str | None = None,
) -> TaskGenerator:
    """Get a task generator for the specified environment and seed.
    
    Args:
        environment_id: Environment identifier
        derivation_seed: Seed for deterministic generation
        generator_family: Generator family (default: "answer")
        version: Generator version (uses default if None)
        
    Returns:
        Configured task generator
        
    Raises:
        ValueError: If generator family or version not found
    """
    factory = get_registry().get(generator_family, version)
    return factory(environment_id=environment_id, derivation_seed=derivation_seed)


# Initialize registry on module import
_initialize_registry()
