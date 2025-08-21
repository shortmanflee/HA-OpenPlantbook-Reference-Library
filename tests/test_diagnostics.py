"""Test the diagnostics module of the Open Plantbook Reference Library integration."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openplantbook_ref.const import DOMAIN
from custom_components.openplantbook_ref.diagnostics import (
    async_get_config_entry_diagnostics,
)


class TestDiagnostics:
    """Test the diagnostics module."""

    async def test_async_get_config_entry_diagnostics_basic(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting basic diagnostics for a config entry."""
        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check main entry data
        assert result["entry_data"]["client_id"] == "**REDACTED**"
        assert result["entry_data"]["secret"] == "**REDACTED**"
        assert result["entry_options"] == {}
        assert result["entry_id"] == mock_config_entry.entry_id
        assert result["entry_title"] == mock_config_entry.title
        assert result["entry_unique_id"] == mock_config_entry.unique_id
        assert result["subentries"] == {}

    async def test_async_get_config_entry_diagnostics_with_runtime_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting diagnostics with runtime data."""
        # Set up hass data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "runtime": "data",
            "client_id": "should_be_redacted",
            "secret": "should_be_redacted",
        }

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check runtime data is included and redacted
        assert "runtime_data" in result
        assert result["runtime_data"]["runtime"] == "data"
        assert result["runtime_data"]["client_id"] == "**REDACTED**"
        assert result["runtime_data"]["secret"] == "**REDACTED**"
