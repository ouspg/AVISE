"""Plugin based registry system for component discovery and use.

Components are registered via decorators, enabling automatic
discovery and flexible use.
"""

from typing import Dict, List, Type, Any


class Registry:
    """Holds information about classes."""

    def __init__(self, name: str):
        self.name = name
        self._items: Dict[str, Type] = {}

    def register(self, name: str):
        """Decorator to register a class.

        Example usage:
            @SET_registry.register("prompt_injection")
        """

        def decorator(cls):
            if name in self._items:
                raise ValueError(f"{self.name}: '{name}' is already registered")
            self._items[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> Type:
        """Get a registered class by name."""
        if name not in self._items:
            raise KeyError(f"{self.name}: '{name}' not found. Available: {self.list()}")
        return self._items[name]

    def create(self, name: str, *args, **kwargs) -> Any:
        """Create an instance of a registered class."""
        cls = self.get(name)
        return cls(*args, **kwargs)

    def list(self) -> List[str]:
        """List all registered names."""
        return list(self._items.keys())


# Make registries global
evaluator_registry = Registry("evaluators")
connector_registry = Registry("connectors")
set_registry = Registry("sets")
