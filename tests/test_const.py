"""Test the const module of the Open Plantbook Reference Library integration."""

from __future__ import annotations

from custom_components.openplantbook_ref.const import generate_device_id


class TestGenerateDeviceId:
    """Test the generate_device_id function."""

    def test_generate_device_id_with_plant_id(self) -> None:
        """Test device ID generation with plant_id."""
        plant_data = {"plant_id": "Test Plant ID", "name": "Test Plant"}

        result = generate_device_id(plant_data)

        assert result == "test_plant_id"

    def test_generate_device_id_with_scientific_name(self) -> None:
        """Test device ID generation with scientific_name when no plant_id."""
        plant_data = {"scientific_name": "Plantus testicus", "name": "Test Plant"}

        result = generate_device_id(plant_data)

        assert result == "plantus_testicus"

    def test_generate_device_id_with_name_fallback(self) -> None:
        """Test device ID generation falling back to name."""
        plant_data = {"name": "Test Plant Name"}

        result = generate_device_id(plant_data)

        assert result == "test_plant_name"

    def test_generate_device_id_empty_plant_data(self) -> None:
        """Test device ID generation with empty plant data."""
        plant_data: dict[str, str] = {}

        result = generate_device_id(plant_data)

        assert result == "unnamed_plant"

    def test_generate_device_id_priority_order(self) -> None:
        """Test that plant_id takes priority over other fields."""
        plant_data = {
            "plant_id": "Primary ID",
            "scientific_name": "Secondary Name",
            "name": "Tertiary Name",
        }

        result = generate_device_id(plant_data)

        assert result == "primary_id"

    def test_generate_device_id_special_characters(self) -> None:
        """Test device ID generation with special characters."""
        plant_data = {"plant_id": "Test Plant #1 (Variety A)"}

        result = generate_device_id(plant_data)

        assert result == "test_plant_1_variety_a"

    def test_generate_device_id_unicode_characters(self) -> None:
        """Test device ID generation with unicode characters."""
        plant_data = {"scientific_name": "Plantárium tëstícus"}

        result = generate_device_id(plant_data)

        assert result == "plantarium_testicus"
