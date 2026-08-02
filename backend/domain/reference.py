"""Framework-neutral factory reference data models.

IDs are stable generated identities. Codes are changeable business labels and
must be unique within their reference-data type when stored. These records do
not define authorization scopes or permissions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


_OPAQUE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _OPAQUE_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a valid opaque identifier")


def _validate_code(value: str) -> None:
    if not isinstance(value, str) or not _CODE_PATTERN.fullmatch(value):
        raise ValueError(
            "code must be non-empty and contain only letters, numbers, '.', "
            "'_' or '-'"
        )


def _validate_name(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("name must not be empty")


def _validate_lifecycle(value: ReferenceLifecycle) -> None:
    if not isinstance(value, ReferenceLifecycle):
        raise TypeError("lifecycle must be a ReferenceLifecycle")


@dataclass(frozen=True, order=True)
class PlantId:
    value: str

    def __post_init__(self) -> None:
        _validate_id(self.value, "plant ID")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class DepartmentId:
    value: str

    def __post_init__(self) -> None:
        _validate_id(self.value, "department ID")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class ProcessId:
    value: str

    def __post_init__(self) -> None:
        _validate_id(self.value, "process ID")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class MachineId:
    value: str

    def __post_init__(self) -> None:
        _validate_id(self.value, "machine ID")

    def __str__(self) -> str:
        return self.value


class ReferenceLifecycle(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class Plant:
    plant_id: PlantId
    code: str
    name: str
    lifecycle: ReferenceLifecycle = ReferenceLifecycle.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.plant_id, PlantId):
            raise TypeError("plant_id must be a PlantId")
        _validate_code(self.code)
        _validate_name(self.name)
        _validate_lifecycle(self.lifecycle)


@dataclass(frozen=True)
class Department:
    department_id: DepartmentId
    plant_id: PlantId
    code: str
    name: str
    lifecycle: ReferenceLifecycle = ReferenceLifecycle.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.department_id, DepartmentId):
            raise TypeError("department_id must be a DepartmentId")
        if not isinstance(self.plant_id, PlantId):
            raise TypeError("plant_id must be a PlantId")
        _validate_code(self.code)
        _validate_name(self.name)
        _validate_lifecycle(self.lifecycle)


@dataclass(frozen=True)
class Process:
    process_id: ProcessId
    plant_id: PlantId
    code: str
    name: str
    department_id: DepartmentId | None = None
    lifecycle: ReferenceLifecycle = ReferenceLifecycle.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.process_id, ProcessId):
            raise TypeError("process_id must be a ProcessId")
        if not isinstance(self.plant_id, PlantId):
            raise TypeError("plant_id must be a PlantId")
        if self.department_id is not None and not isinstance(
            self.department_id,
            DepartmentId,
        ):
            raise TypeError("department_id must be a DepartmentId or None")
        _validate_code(self.code)
        _validate_name(self.name)
        _validate_lifecycle(self.lifecycle)


@dataclass(frozen=True)
class Machine:
    machine_id: MachineId
    process_id: ProcessId
    plant_id: PlantId
    code: str
    name: str
    lifecycle: ReferenceLifecycle = ReferenceLifecycle.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.machine_id, MachineId):
            raise TypeError("machine_id must be a MachineId")
        if not isinstance(self.process_id, ProcessId):
            raise TypeError("process_id must be a ProcessId")
        if not isinstance(self.plant_id, PlantId):
            raise TypeError("plant_id must be a PlantId")
        _validate_code(self.code)
        _validate_name(self.name)
        _validate_lifecycle(self.lifecycle)
