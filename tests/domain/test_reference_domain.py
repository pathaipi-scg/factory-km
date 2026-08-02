"""Focused tests for core reference data phase 2."""

import unittest
from dataclasses import replace

from backend.domain import (
    Department,
    DepartmentId,
    Machine,
    MachineId,
    Plant,
    PlantId,
    Process,
    ProcessId,
    ReferenceLifecycle,
)


class ReferenceDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plant_id = PlantId("plant-01KM")
        self.department_id = DepartmentId("department-01KM")
        self.process_id = ProcessId("process-01KM")

    def test_generated_identity_is_independent_of_changeable_code(self) -> None:
        plant = Plant(self.plant_id, "BKK-01", "Bangkok Plant")
        renamed = replace(plant, code="BKK-MAIN", name="Bangkok Main Plant")

        self.assertEqual(renamed.plant_id, plant.plant_id)
        self.assertNotEqual(renamed.code, plant.code)

    def test_department_belongs_to_plant(self) -> None:
        department = Department(
            self.department_id,
            self.plant_id,
            "MAINT",
            "Maintenance",
        )

        self.assertEqual(department.plant_id, self.plant_id)

    def test_process_belongs_to_plant_and_department_is_optional(self) -> None:
        plant_process = Process(
            self.process_id,
            self.plant_id,
            "PACK",
            "Packaging",
        )
        department_process = replace(
            plant_process,
            department_id=self.department_id,
        )

        self.assertIsNone(plant_process.department_id)
        self.assertEqual(department_process.department_id, self.department_id)
        self.assertEqual(department_process.plant_id, self.plant_id)

    def test_machine_belongs_to_process_and_plant(self) -> None:
        machine = Machine(
            MachineId("machine-01KM"),
            self.process_id,
            self.plant_id,
            "FILLER-01",
            "Filling Machine 1",
        )

        self.assertEqual(machine.process_id, self.process_id)
        self.assertEqual(machine.plant_id, self.plant_id)

    def test_inactive_reference_records_are_preserved(self) -> None:
        plant = Plant(
            self.plant_id,
            "OLD-PLANT",
            "Legacy Plant",
            ReferenceLifecycle.INACTIVE,
        )

        self.assertEqual(plant.lifecycle, ReferenceLifecycle.INACTIVE)
        self.assertFalse(hasattr(plant, "permissions"))
        self.assertFalse(hasattr(plant, "scopes"))

    def test_invalid_identity_code_and_name_are_rejected(self) -> None:
        invalid_factories = (
            lambda: PlantId("factory/plant"),
            lambda: Plant(self.plant_id, "invalid code", "Plant"),
            lambda: Plant(self.plant_id, "VALID", "  "),
        )

        for factory in invalid_factories:
            with self.subTest(factory=factory):
                with self.assertRaises(ValueError):
                    factory()

    def test_relationships_require_typed_stable_ids(self) -> None:
        with self.assertRaises(TypeError):
            Department(
                self.department_id,
                "plant-code",  # type: ignore[arg-type]
                "MAINT",
                "Maintenance",
            )

        with self.assertRaises(TypeError):
            Machine(
                MachineId("machine-01KM"),
                "process-code",  # type: ignore[arg-type]
                self.plant_id,
                "FILLER-01",
                "Filling Machine 1",
            )


if __name__ == "__main__":
    unittest.main()
