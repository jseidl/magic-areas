"""Config Flow for Magic Area."""

# Re-export from new modular structure for backward compatibility
from .config_flow.flow import (
    ConfigBase,
    ConfigFlow,
    NullableEntitySelector,
    OptionsFlowHandler,
)

__all__ = [
    "ConfigBase",
    "ConfigFlow",
    "NullableEntitySelector",
    "OptionsFlowHandler",
]
