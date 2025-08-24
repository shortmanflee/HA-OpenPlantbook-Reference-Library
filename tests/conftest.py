"""Pytest configuration for the Open Plantbook Reference Library integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.openplantbook_ref.const import DOMAIN


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Plant Sensor",
        data={
            "client_id": "test_client_id",
            "secret": "test_secret",
        },
        entry_id="test_entry_id",
        version=1,
        minor_version=1,
    )


@pytest.fixture
def mock_plant_data() -> dict[str, str | int | list[str]]:
    """Return mock plant data."""
    return {
        "name": "Test Plant",
        "plant_id": "test_plant_id",
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
        "entity_picture": "/local/plants/test_plant.jpg",
    }


@pytest.fixture
def mock_openplantbook_search_result() -> dict[
    str, list[dict[str, str | int | list[str]]]
]:
    """Return mock OpenPlantBook search result."""
    return {
        "results": [
            {
                "pid": "test_plant_123",
                "display_pid": "test_plant_123",
                "alias": "Test Plant",
                "max_light_mmol": 1500,
                "min_light_mmol": 500,
                "max_light_lux": 30000,
                "min_light_lux": 10000,
                "max_temp": 25,
                "min_temp": 18,
                "max_env_humid": 60,
                "min_env_humid": 40,
                "max_soil_moist": 70,
                "min_soil_moist": 30,
                "max_soil_ec": 2000,
                "min_soil_ec": 350,
                "image_url": "https://example.com/plant_image.jpg",
                "scientific_name": ["Plantus testicus"],
                "common_name": ["Test Plant"],
                "category": ["Indoor", "Easy Care"],
                "other_name": ["Alternative Test Plant"],
            }
        ]
    }


@pytest.fixture
def mock_openplantbook_detail() -> dict[str, str | int | list[str]]:
    """Return mock OpenPlantBook plant detail."""
    return {
        "pid": "test_plant_123",
        "display_pid": "test_plant_123",
        "alias": "Test Plant",
        "max_light_mmol": 1500,
        "min_light_mmol": 500,
        "max_light_lux": 30000,
        "min_light_lux": 10000,
        "max_temp": 25,
        "min_temp": 18,
        "max_env_humid": 60,
        "min_env_humid": 40,
        "max_soil_moist": 70,
        "min_soil_moist": 30,
        "max_soil_ec": 2000,
        "min_soil_ec": 350,
        "image_url": "https://example.com/plant_image.jpg",
        "scientific_name": ["Plantus testicus"],
        "common_name": ["Test Plant"],
        "category": ["Indoor", "Easy Care"],
        "other_name": ["Alternative Test Plant"],
        "blooming_months": ["March", "April", "May"],
        "pruning_months": ["January", "February"],
        "origin": ["Test Region"],
        "climatic_resistance": "Zone 9-11",
    }


@pytest.fixture
async def mock_hass(hass: HomeAssistant) -> HomeAssistant:
    """Return a Home Assistant instance with domain data initialized."""
    hass.data.setdefault(DOMAIN, {})
    return hass
