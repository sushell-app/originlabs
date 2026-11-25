"""Extensions module: core contracts for licensing and Sushell first-party services."""

from app.modules.extensions.contracts import (
    CommunityLicenseProvider,
    ExtensionDescriptor,
    ExtensionRegistry,
    LicenseInfo,
    LicenseProvider,
    build_default_registry,
)

__all__ = [
    "CommunityLicenseProvider",
    "ExtensionDescriptor",
    "ExtensionRegistry",
    "LicenseInfo",
    "LicenseProvider",
    "build_default_registry",
]
