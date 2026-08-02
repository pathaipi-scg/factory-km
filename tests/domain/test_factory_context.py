"""Focused tests for the framework-neutral Factory Context models."""

import unittest
from dataclasses import FrozenInstanceError, replace

from backend.domain.factory_context import (
    FactoryConfiguration,
    FactoryContext,
    FactoryIdentity,
)


class FactoryContextTests(unittest.TestCase):
    @staticmethod
    def configuration(*, is_active: bool = True) -> FactoryConfiguration:
        return FactoryConfiguration(
            plant_code="BKK-01",
            database_name="factory-km",
            vault_root=r"D:\Factory-KM\Vault",
            pageindex_workspace=r"D:\Factory-KM\PageIndex",
            dictionary_root=r"D:\Factory-KM\Dictionary",
            wiki_root=r"D:\Factory-KM\Wiki",
            chat_namespace="factory-bkk-01",
            is_active=is_active,
        )

    def test_context_relates_stable_identity_to_configuration(self) -> None:
        identity = FactoryIdentity("factory-01KM")
        configuration = self.configuration()
        context = FactoryContext(identity, configuration)

        self.assertEqual(context.identity, identity)
        self.assertEqual(context.configuration, configuration)
        self.assertEqual(context.configuration.plant_code, "BKK-01")

    def test_identity_is_independent_of_changeable_plant_code(self) -> None:
        context = FactoryContext(
            FactoryIdentity("factory-01KM"),
            self.configuration(),
        )
        renamed = replace(
            context,
            configuration=replace(context.configuration, plant_code="BKK-MAIN"),
        )

        self.assertEqual(renamed.identity, context.identity)
        self.assertNotEqual(
            renamed.configuration.plant_code,
            context.configuration.plant_code,
        )

    def test_inactive_factory_configuration_is_representable(self) -> None:
        context = FactoryContext(
            FactoryIdentity("factory-inactive"),
            self.configuration(is_active=False),
        )

        self.assertFalse(context.configuration.is_active)

    def test_models_are_immutable_configuration_snapshots(self) -> None:
        configuration = self.configuration()

        with self.assertRaises(FrozenInstanceError):
            configuration.database_name = "replacement"  # type: ignore[misc]

    def test_invalid_identity_and_required_configuration_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FactoryIdentity(r"D:\Factory-KM")
        with self.assertRaises(ValueError):
            replace(self.configuration(), vault_root="  ")
        with self.assertRaises(ValueError):
            replace(self.configuration(), plant_code="plant code")
        with self.assertRaises(TypeError):
            replace(self.configuration(), is_active=1)  # type: ignore[arg-type]

    def test_context_requires_typed_identity_and_configuration(self) -> None:
        with self.assertRaises(TypeError):
            FactoryContext("factory-01KM", self.configuration())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            FactoryContext(FactoryIdentity("factory-01KM"), {})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
