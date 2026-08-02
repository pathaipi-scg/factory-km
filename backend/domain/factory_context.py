"""Framework-neutral runtime context for one factory plant."""

import re
from dataclasses import dataclass


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a valid non-empty identifier")


def _validate_location(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, order=True)
class FactoryIdentity:
    """Stable generated identity for a factory, independent of plant code."""

    value: str

    def __post_init__(self) -> None:
        _validate_identifier(self.value, "factory identity")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class FactoryConfiguration:
    """Configuration snapshot for one factory's isolated runtime resources."""

    plant_code: str
    database_name: str
    vault_root: str
    pageindex_workspace: str
    dictionary_root: str
    wiki_root: str
    chat_namespace: str
    is_active: bool = True

    def __post_init__(self) -> None:
        _validate_identifier(self.plant_code, "plant code")
        _validate_identifier(self.database_name, "database name")
        _validate_location(self.vault_root, "Vault root")
        _validate_location(self.pageindex_workspace, "PageIndex workspace")
        _validate_location(self.dictionary_root, "Dictionary root")
        _validate_location(self.wiki_root, "Wiki root")
        _validate_identifier(self.chat_namespace, "chat namespace")
        if type(self.is_active) is not bool:
            raise TypeError("is_active must be a bool")


@dataclass(frozen=True)
class FactoryContext:
    """Runtime domain context pairing one factory with its configuration."""

    identity: FactoryIdentity
    configuration: FactoryConfiguration

    def __post_init__(self) -> None:
        if not isinstance(self.identity, FactoryIdentity):
            raise TypeError("identity must be a FactoryIdentity")
        if not isinstance(self.configuration, FactoryConfiguration):
            raise TypeError("configuration must be a FactoryConfiguration")
