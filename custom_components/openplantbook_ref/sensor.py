"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
    entities = [
        PlantSensor(
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
        ),
    ]

    _LOGGER.debug("Created %d entities for device %s", len(entities), device_id)
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
):
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

    def __init__(
        self,
        name: str,
        device_id: str,
        entity_picture: str | None = None,
        plant_id: str | None = None,
        scientific_name: str | None = None,
        common_name: str | None = None,
        categories: list[str] | None = None,
        friendly_name: str | None = None,
        min_light: int | None = None,
        max_light: int | None = None,
        min_temp: int | None = None,
        max_temp: int | None = None,
        min_humidity: int | None = None,
        max_humidity: int | None = None,
        min_moisture: int | None = None,
        max_moisture: int | None = None,
        min_soil_ec: int | None = None,
        max_soil_ec: int | None = None,
    ) -> None:
        """Initialize the PlantSensor with all plant data."""
        _LOGGER.debug(
            "Initializing PlantSensor: name=%s, device_id=%s", name, device_id
        )

        self._device_id = device_id
        self._plant_name = name
        self._attr_name = "Plant"
        self._attr_unique_id = f"{device_id}_plant"
        self._attr_entity_picture = entity_picture

        # Store plant metadata
        self._plant_id = plant_id
        self._scientific_name = scientific_name
        self._common_name = common_name
        self._categories = categories
        self._friendly_name = friendly_name

        # Store min/max values
        self._min_light = min_light
        self._max_light = max_light
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._min_humidity = min_humidity
        self._max_humidity = max_humidity
        self._min_moisture = min_moisture
        self._max_moisture = max_moisture
        self._min_soil_ec = min_soil_ec
        self._max_soil_ec = max_soil_ec

        # Set up device info (from the old base class)
        model_name = (
            scientific_name
            if scientific_name and scientific_name.strip()
            else "Plant Reference"
        )
        model_id = plant_id if plant_id else device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=name,
            manufacturer="Plant Reference",
            model=model_name,
            model_id=model_id,
        )

        _LOGGER.debug(
            "PlantSensor initialized - unique_id: %s, model: %s, categories: %s",
            self._attr_unique_id,
            model_name,
            categories,
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
    def extra_state_attributes(self) -> dict[str, any]:
        """Return the extra state attributes."""
        attributes = {}

        # Basic plant info
        if self._scientific_name:
            attributes["scientific_name"] = self._scientific_name
        if self._common_name:
            attributes["common_name"] = self._common_name
        if self._categories:
            attributes["categories"] = self._categories
        if self._plant_id:
            attributes["plant_id"] = self._plant_id

        # Light attributes
        if self._min_light is not None:
            attributes["minimum_light"] = self._min_light
        if self._max_light is not None:
            attributes["maximum_light"] = self._max_light

        # Temperature attributes
        if self._min_temp is not None:
            attributes["minimum_temperature"] = self._min_temp
        if self._max_temp is not None:
            attributes["maximum_temperature"] = self._max_temp

        # Humidity attributes
        if self._min_humidity is not None:
            attributes["minimum_humidity"] = self._min_humidity
        if self._max_humidity is not None:
            attributes["maximum_humidity"] = self._max_humidity

        # Moisture attributes
        if self._min_moisture is not None:
            attributes["minimum_moisture"] = self._min_moisture
        if self._max_moisture is not None:
            attributes["maximum_moisture"] = self._max_moisture

        # Soil EC attributes
        if self._min_soil_ec is not None:
            attributes["minimum_soil_ec"] = self._min_soil_ec
        if self._max_soil_ec is not None:
            attributes["maximum_soil_ec"] = self._max_soil_ec

        return attributes
