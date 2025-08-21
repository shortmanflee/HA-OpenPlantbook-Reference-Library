"""Test the sensor module of the Open Plantbook Reference Library integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from custom_components.openplantbook_ref.const import DOMAIN
from custom_components.openplantbook_ref.sensor import (
    PlantConfig,
    PlantSensor,
    _create_device_entities,
    async_setup_entry,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


class TestPlantConfig:
    """Test the PlantConfig dataclass."""

    def test_plant_config_creation(self) -> None:
        """Test PlantConfig creation with all parameters."""
        config = PlantConfig(
            name="Test Plant",
            device_id="test_device",
            entity_picture="/path/to/image.jpg",
            plant_id="test_plant_123",
            scientific_name="Plantus testicus",
            common_name="Test Plant Common",
            categories=["Indoor", "Easy Care"],
            friendly_name="My Test Plant",
            min_light=1000,
            max_light=3000,
            min_temp=18,
            max_temp=25,
            min_humidity=40,
            max_humidity=60,
            min_moisture=30,
            max_moisture=70,
            min_soil_ec=350,
            max_soil_ec=2000,
        )

        assert config.name == "Test Plant"
        assert config.device_id == "test_device"
        assert config.entity_picture == "/path/to/image.jpg"
        assert config.plant_id == "test_plant_123"
        assert config.scientific_name == "Plantus testicus"
        assert config.common_name == "Test Plant Common"
        assert config.categories == ["Indoor", "Easy Care"]
        assert config.friendly_name == "My Test Plant"
        assert config.min_light == 1000
        assert config.max_light == 3000
        assert config.min_temp == 18
        assert config.max_temp == 25
        assert config.min_humidity == 40
        assert config.max_humidity == 60
        assert config.min_moisture == 30
        assert config.max_moisture == 70
        assert config.min_soil_ec == 350
        assert config.max_soil_ec == 2000

    def test_plant_config_defaults(self) -> None:
        """Test PlantConfig with default values."""
        config = PlantConfig(name="Test Plant", device_id="test_device")

        assert config.name == "Test Plant"
        assert config.device_id == "test_device"
        assert config.entity_picture is None
        assert config.plant_id is None
        assert config.scientific_name is None
        assert config.common_name is None
        assert config.categories is None
        assert config.friendly_name is None
        assert config.min_light is None
        assert config.max_light is None
        assert config.min_temp is None
        assert config.max_temp is None
        assert config.min_humidity is None
        assert config.max_humidity is None
        assert config.min_moisture is None
        assert config.max_moisture is None
        assert config.min_soil_ec is None
        assert config.max_soil_ec is None


class TestCreateDeviceEntities:
    """Test the _create_device_entities function."""

    def test_create_device_entities_full_data(self) -> None:
        """Test creating device entities with full plant data."""
        device_info = {
            "name": "Test Plant",
            "plant_id": "test_plant_123",
            "scientific_name": "Plantus testicus",
            "common_name": "Test Plant Common",
            "categories": ["Indoor", "Easy Care"],
            "friendly_name": "My Test Plant",
            "min_light": 1000,
            "max_light": 3000,
            "min_temp": 18,
            "max_temp": 25,
            "min_humidity": 40,
            "max_humidity": 60,
            "min_moisture": 30,
            "max_moisture": 70,
            "min_soil_ec": 350,
            "max_soil_ec": 2000,
            "entity_picture": "/path/to/image.jpg",
        }
        device_id = "test_device"

        entities = _create_device_entities(device_info, device_id)

        assert len(entities) == 1
        assert isinstance(entities[0], PlantSensor)

        # Check that entities are created correctly
        sensor = entities[0]
        assert isinstance(sensor, PlantSensor)
        assert sensor.unique_id == "test_device_plant"
        assert sensor.name == "Plant"
        assert sensor.entity_picture == "/path/to/image.jpg"

    def test_create_device_entities_minimal_data(self) -> None:
        """Test creating device entities with minimal plant data."""
        device_info = {"name": "Minimal Plant"}
        device_id = "minimal_device"

        entities = _create_device_entities(device_info, device_id)

        assert len(entities) == 1
        assert isinstance(entities[0], PlantSensor)

        sensor = entities[0]
        assert sensor.unique_id == "minimal_device_plant"

    def test_create_device_entities_unnamed_plant(self) -> None:
        """Test creating device entities with unnamed plant."""
        device_info: dict[str, str] = {}
        device_id = "unnamed_device"

        entities = _create_device_entities(device_info, device_id)

        assert len(entities) == 1
        sensor = entities[0]
        assert sensor.unique_id == "unnamed_device_plant"


class TestPlantSensor:
    """Test the PlantSensor class."""

    def test_plant_sensor_initialization(self) -> None:
        """Test PlantSensor initialization."""
        config = PlantConfig(
            name="Test Plant",
            device_id="test_device",
            plant_id="test_plant_123",
            scientific_name="Plantus testicus",
            min_light=1000,
            max_light=3000,
        )

        sensor = PlantSensor(config)

        assert sensor.name == "Plant"
        assert sensor.unique_id == "test_device_plant"

    def test_plant_sensor_native_value_with_friendly_name(self) -> None:
        """Test PlantSensor native value with friendly name."""
        config = PlantConfig(
            name="Test Plant",
            device_id="test_device",
            friendly_name="My Test Plant",
        )

        sensor = PlantSensor(config)

        assert sensor.native_value == "My Test Plant"

    def test_plant_sensor_native_value_without_friendly_name(self) -> None:
        """Test PlantSensor native value without friendly name."""
        config = PlantConfig(
            name="Test Plant",
            device_id="test_device",
        )

        sensor = PlantSensor(config)

        assert sensor.native_value == "Test Plant"

    def test_plant_sensor_extra_state_attributes(self) -> None:
        """Test PlantSensor extra state attributes."""
        config = PlantConfig(
            name="Test Plant",
            device_id="test_device",
            plant_id="test_plant_123",
            scientific_name="Plantus testicus",
            common_name="Test Plant Common",
            categories=["Indoor", "Easy Care"],
            friendly_name="My Test Plant",
            min_light=1000,
            max_light=3000,
            min_temp=18,
            max_temp=25,
            min_humidity=40,
            max_humidity=60,
            min_moisture=30,
            max_moisture=70,
            min_soil_ec=350,
            max_soil_ec=2000,
        )

        sensor = PlantSensor(config)
        attributes = sensor.extra_state_attributes

        assert attributes["plant_id"] == "test_plant_123"
        assert attributes["scientific_name"] == "Plantus testicus"
        assert attributes["common_name"] == "Test Plant Common"
        assert attributes["categories"] == ["Indoor", "Easy Care"]
        # friendly_name is not in attributes, it's used for native_value
        assert attributes["minimum_light"] == 1000
        assert attributes["maximum_light"] == 3000
        assert attributes["minimum_temperature"] == 18
        assert attributes["maximum_temperature"] == 25
        assert attributes["minimum_humidity"] == 40
        assert attributes["maximum_humidity"] == 60
        assert attributes["minimum_moisture"] == 30
        assert attributes["maximum_moisture"] == 70
        assert attributes["minimum_soil_ec"] == 350
        assert attributes["maximum_soil_ec"] == 2000

    def test_plant_sensor_extra_state_attributes_none_values(self) -> None:
        """Test PlantSensor extra state attributes with None values."""
        config = PlantConfig(name="Test Plant", device_id="test_device")

        sensor = PlantSensor(config)
        attributes = sensor.extra_state_attributes

        # None values should not be included in attributes
        assert "plant_id" not in attributes
        assert "scientific_name" not in attributes
        assert "common_name" not in attributes
        assert "categories" not in attributes
        assert "minimum_light" not in attributes
        assert "maximum_light" not in attributes
        assert "minimum_temperature" not in attributes
        assert "maximum_temperature" not in attributes
        assert "minimum_humidity" not in attributes
        assert "maximum_humidity" not in attributes
        assert "minimum_moisture" not in attributes
        assert "maximum_moisture" not in attributes
        assert "minimum_soil_ec" not in attributes
        assert "maximum_soil_ec" not in attributes

    def test_plant_sensor_device_info(self) -> None:
        """Test PlantSensor device info."""
        config = PlantConfig(
            name="Test Plant",
            device_id="test_device",
            plant_id="test_plant_123",
        )

        sensor = PlantSensor(config)
        device_info = sensor.device_info

        assert device_info["identifiers"] == {(DOMAIN, "test_device")}
        assert device_info["name"] == "Test Plant"
        assert device_info["manufacturer"] == "Plant Reference"

    def test_plant_sensor_entity_picture(self) -> None:
        """Test PlantSensor entity picture."""
        config = PlantConfig(
            name="Test Plant",
            device_id="test_device",
            entity_picture="/path/to/image.jpg",
        )

        sensor = PlantSensor(config)

        assert sensor.entity_picture == "/path/to/image.jpg"

    def test_plant_sensor_entity_picture_none(self) -> None:
        """Test PlantSensor entity picture when None."""
        config = PlantConfig(name="Test Plant", device_id="test_device")

        sensor = PlantSensor(config)

        assert sensor.entity_picture is None


class TestAsyncSetupEntry:
    """Test the async_setup_entry function."""

    async def test_async_setup_entry_with_subentries(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test async_setup_entry with subentries."""
        # Mock the config entry with subentries
        mock_subentry = Mock()
        mock_subentry.data = {
            "name": "Test Plant",
            "device_id": "test_device",
            "plant_id": "test_plant_123",
        }

        with (
            patch.object(mock_config_entry, "subentries", {"sub1": mock_subentry}),
            patch(
                "custom_components.openplantbook_ref.sensor._create_device_entities"
            ) as mock_create_entities,
        ):
            mock_entities = [Mock()]
            mock_create_entities.return_value = mock_entities

            mock_async_add_entities = Mock()

            await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

            # device_id is stripped when passed to _create_device_entities
            expected_device_info = {"name": "Test Plant", "plant_id": "test_plant_123"}
            mock_create_entities.assert_called_once_with(
                expected_device_info, "test_device"
            )
            mock_async_add_entities.assert_called_once_with(
                mock_entities, config_subentry_id="sub1"
            )

    async def test_async_setup_entry_no_subentries(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test async_setup_entry with no subentries."""
        mock_async_add_entities = Mock()

        await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

        # No entities should be added when there are no subentries
        mock_async_add_entities.assert_not_called()

    async def test_async_setup_entry_multiple_subentries(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test async_setup_entry with multiple subentries."""
        mock_subentry1 = Mock()
        mock_subentry1.data = {
            "name": "Plant 1",
            "device_id": "device_1",
        }
        mock_subentry2 = Mock()
        mock_subentry2.data = {
            "name": "Plant 2",
            "device_id": "device_2",
        }

        with (
            patch.object(
                mock_config_entry,
                "subentries",
                {"sub1": mock_subentry1, "sub2": mock_subentry2},
            ),
            patch(
                "custom_components.openplantbook_ref.sensor._create_device_entities"
            ) as mock_create_entities,
        ):
            mock_create_entities.return_value = [Mock()]
            mock_async_add_entities = Mock()

            await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

            # Should be called twice, once for each subentry
            assert mock_create_entities.call_count == 2
            # Should add entities separately for each subentry (not all at once)
            assert mock_async_add_entities.call_count == 2
