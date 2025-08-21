"""Platform for sensor integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from custom_components.openplantbook_ref.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlantConfig:
    """Configuration data for a plant sensor."""

    name: str
    device_id: str
    entity_picture: str | None = None
    plant_id: str | None = None
    scientific_name: str | None = None
    common_name: str | None = None
    categories: list[str] | None = None
    friendly_name: str | None = None
    min_light: int | None = None
    max_light: int | None = None
    min_temp: int | None = None
    max_temp: int | None = None
    min_humidity: int | None = None
    max_humidity: int | None = None
    min_moisture: int | None = None
    max_moisture: int | None = None
    min_soil_ec: int | None = None
    max_soil_ec: int | None = None


def _create_device_entities(device_info: dict, device_id: str) -> list[PlantSensor]:
    """Create sensor entities for a single device."""
    _LOGGER.debug("Creating device entities for device_id: %s", device_id)
    _LOGGER.debug("Device info keys: %s", list(device_info.keys()))

    name = device_info.get("name", "Unnamed Plant")
    plant_id = device_info.get("plant_id")
    scientific_name = device_info.get("scientific_name")
    common_name = device_info.get("common_name")
    categories = device_info.get("categories")
    friendly_name = device_info.get("friendly_name")

    min_light = device_info.get("min_light", 0)
    max_light = device_info.get("max_light", 100)
    min_temp = device_info.get("min_temp")
    max_temp = device_info.get("max_temp")
    min_humidity = device_info.get("min_humidity")
    max_humidity = device_info.get("max_humidity")
    min_moisture = device_info.get("min_moisture")
    max_moisture = device_info.get("max_moisture")
    min_soil_ec = device_info.get("min_soil_ec")
    max_soil_ec = device_info.get("max_soil_ec")
    entity_picture = device_info.get("entity_picture")

    _LOGGER.debug(
        "Creating PlantSensor entity: name=%s, plant_id=%s, scientific_name=%s",
        name,
        plant_id,
        scientific_name,
    )

    # Create single plant entity with all min/max values as attributes
    config = PlantConfig(
        name=name,
        device_id=device_id,
        entity_picture=entity_picture,
        plant_id=plant_id,
        scientific_name=scientific_name,
        common_name=common_name,
        categories=categories,
        friendly_name=friendly_name,
        min_light=min_light,
        max_light=max_light,
        min_temp=min_temp,
        max_temp=max_temp,
        min_humidity=min_humidity,
        max_humidity=max_humidity,
        min_moisture=min_moisture,
        max_moisture=max_moisture,
        min_soil_ec=min_soil_ec,
        max_soil_ec=max_soil_ec,
    )

    entities = [
        PlantSensor(config),
    ]

    _LOGGER.debug("Created %d entities for device %s", len(entities), device_id)
    return entities


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up plant sensor entities from config entry."""
    _LOGGER.info("Setting up sensor platform for entry: %s", entry.entry_id)
    _LOGGER.debug(
        "Config entry details - ID: %s, type: %s, title: %s",
        entry.entry_id,
        type(entry).__name__,
        entry.title,
    )
    _LOGGER.debug("Config entry data keys: %s", list(entry.data.keys()))

    entities = []

    # Check if this is a subentry (contains device_id)
    if "device_id" in entry.data:
        # This is a subentry for a single device
        device_id = entry.data["device_id"]
        device_info = {k: v for k, v in entry.data.items() if k != "device_id"}
        _LOGGER.info("Processing subentry with device_id: %s", device_id)
        _LOGGER.debug("Device info for %s: %s", device_id, device_info)
        entities.extend(_create_device_entities(device_info, device_id))
    else:
        # This is the main entry - process subentries only
        _LOGGER.info("Processing main entry with %d subentries", len(entry.subentries))
        for subentry_id, subentry in entry.subentries.items():
            _LOGGER.debug(
                "Processing subentry %s with data: %s",
                subentry.subentry_id,
                subentry.data,
            )
            if "device_id" in subentry.data:
                device_id = subentry.data["device_id"]
                device_info = {
                    k: v for k, v in subentry.data.items() if k != "device_id"
                }
                _LOGGER.debug("Creating entities for subentry device: %s", device_id)
                subentry_entities = _create_device_entities(device_info, device_id)
                # Add entities with proper subentry association
                _LOGGER.debug(
                    "Adding %d entities for subentry %s",
                    len(subentry_entities),
                    subentry_id,
                )
                async_add_entities(subentry_entities, config_subentry_id=subentry_id)
            else:
                _LOGGER.warning("Subentry %s missing device_id", subentry_id)

    if entities:
        _LOGGER.info(
            "Adding %d entities for config entry %s", len(entities), entry.entry_id
        )
        async_add_entities(entities)
    else:
        _LOGGER.debug("No direct entities to add for config entry %s", entry.entry_id)


class PlantSensor(SensorEntity):
    """Consolidated plant sensor with all plant data."""

    _attr_translation_key = "plant"
    _attr_has_entity_name = True
    _attr_should_poll = False

    _unrecorded_attributes = frozenset(
        {
            "scientific_name",
            "common_name",
            "categories",
            "plant_id",
            "minimum_light",
            "maximum_light",
            "minimum_temperature",
            "maximum_temperature",
            "minimum_humidity",
            "maximum_humidity",
            "minimum_moisture",
            "maximum_moisture",
            "minimum_soil_ec",
            "maximum_soil_ec",
        }
    )

    def __init__(self, config: PlantConfig) -> None:
        """Initialize the PlantSensor with plant configuration data."""
        _LOGGER.debug(
            "Initializing PlantSensor: name=%s, device_id=%s",
            config.name,
            config.device_id,
        )

        self._device_id = config.device_id
        self._plant_name = config.name
        self._attr_name = "Plant"
        self._attr_unique_id = f"{config.device_id}_plant"
        self._attr_entity_picture = config.entity_picture

        # Store plant metadata
        self._plant_id = config.plant_id
        self._scientific_name = config.scientific_name
        self._common_name = config.common_name
        self._categories = config.categories
        self._friendly_name = config.friendly_name

        # Store min/max values
        self._min_light = config.min_light
        self._max_light = config.max_light
        self._min_temp = config.min_temp
        self._max_temp = config.max_temp
        self._min_humidity = config.min_humidity
        self._max_humidity = config.max_humidity
        self._min_moisture = config.min_moisture
        self._max_moisture = config.max_moisture
        self._min_soil_ec = config.min_soil_ec
        self._max_soil_ec = config.max_soil_ec

        # Set up device info (from the old base class)
        model_name = (
            config.scientific_name
            if config.scientific_name and config.scientific_name.strip()
            else "Plant Reference"
        )
        model_id = config.plant_id if config.plant_id else config.device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config.device_id)},
            name=config.name,
            manufacturer="Plant Reference",
            model=model_name,
            model_id=model_id,
        )

        _LOGGER.debug(
            "PlantSensor initialized - unique_id: %s, model: %s, categories: %s",
            self._attr_unique_id,
            model_name,
            config.categories,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        _LOGGER.info(
            "Plant sensor %s being added to Home Assistant", self._attr_unique_id
        )
        await super().async_added_to_hass()
        # Set the initial state from the native_value property
        self._attr_native_value = self.native_value
        _LOGGER.debug(
            "Plant sensor %s native value set to: %s",
            self._attr_unique_id,
            self._attr_native_value,
        )

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        # Return friendly_name if available, otherwise the display name
        return self._friendly_name or self._plant_name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes."""
        attributes = {}

        # Basic plant info - Group basic attributes together
        basic_attrs = {
            "scientific_name": self._scientific_name,
            "common_name": self._common_name,
            "categories": self._categories,
            "plant_id": self._plant_id,
        }
        attributes.update({k: v for k, v in basic_attrs.items() if v is not None})

        # Min/Max attributes - Group ranges together
        range_attrs = [
            ("minimum_light", self._min_light),
            ("maximum_light", self._max_light),
            ("minimum_temperature", self._min_temp),
            ("maximum_temperature", self._max_temp),
            ("minimum_humidity", self._min_humidity),
            ("maximum_humidity", self._max_humidity),
            ("minimum_moisture", self._min_moisture),
            ("maximum_moisture", self._max_moisture),
            ("minimum_soil_ec", self._min_soil_ec),
            ("maximum_soil_ec", self._max_soil_ec),
        ]

        attributes.update(
            {
                attr_name: attr_value
                for attr_name, attr_value in range_attrs
                if attr_value is not None
            }
        )

        return attributes
