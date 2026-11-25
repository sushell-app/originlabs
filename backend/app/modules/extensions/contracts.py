"""Minimal Open Core contracts for licensing and extension registration."""

from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class LicenseInfo:
    """Active edition and enabled commercial entitlements for the instance."""

    edition: Literal["community", "pro", "cloud", "enterprise"] = "community"
    valid: bool = True
    features: tuple[str, ...] = ()


class LicenseProvider(Protocol):
    """Contract for resolving active OriginLabs license entitlements."""

    def get_license(self) -> LicenseInfo:
        """Return the active license metadata for this instance."""
        ...


class CommunityLicenseProvider:
    """Default open-source Community edition provider for MVP/Beta."""

    def get_license(self) -> LicenseInfo:
        """Always return the free Community edition."""
        return LicenseInfo(edition="community", valid=True, features=())


@dataclass(frozen=True, slots=True)
class ExtensionDescriptor:
    """Metadata describing a core module or Sushell first-party extension."""

    id: str
    name: str
    description: str
    kind: Literal["core_included", "extension", "commercial"]
    enabled: bool = True
    requires_license: bool = False


@dataclass
class ExtensionRegistry:
    """In-memory registry for installed Core modules and future Sushell services."""

    _extensions: dict[str, ExtensionDescriptor] = field(default_factory=dict)

    def register(self, descriptor: ExtensionDescriptor) -> None:
        """Register or update an extension descriptor."""
        self._extensions[descriptor.id] = descriptor

    def list_all(self) -> list[ExtensionDescriptor]:
        """Return all registered extensions sorted by registration order."""
        return list(self._extensions.values())


def build_default_registry() -> ExtensionRegistry:
    """Create the default registry containing the included MVP core modules."""
    registry = ExtensionRegistry()
    registry.register(
        ExtensionDescriptor(
            id="projects",
            name="Projects",
            description="Proyectos, equipos y repositorios (GitHub / GitLab).",
            kind="core_included",
            enabled=True,
            requires_license=False,
        )
    )
    registry.register(
        ExtensionDescriptor(
            id="workspaces",
            name="Workspaces",
            description="IDE en el navegador, terminales y entornos aislados.",
            kind="core_included",
            enabled=True,
            requires_license=False,
        )
    )
    return registry
