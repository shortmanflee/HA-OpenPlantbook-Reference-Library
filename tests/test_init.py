"""Test the __init__.py module of the Open Plantbook Reference Library integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.openplantbook_ref import (
    async_remove_config_entry_device,
    async_setup,
    async_setup_entry,
    async_unload_entry,
    async_update_entry,
)
from custom_components.openplantbook_ref.const import DOMAIN

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


class TestInit:
    """Test the integration initialization functions."""

    async def test_async_setup(self, hass: HomeAssistant) -> None:
        """Test async_setup always returns True."""
        result = await async_setup(hass, {})
        assert result is True

    async def test_async_setup_entry_success(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test successful setup of config entry."""
        with patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ) as mock_forward:
            mock_forward.return_value = True

            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert (
                hass.data[DOMAIN][mock_config_entry.entry_id] == mock_config_entry.data
            )
            mock_forward.assert_called_once_with(mock_config_entry, ["sensor"])

            # Check log messages
            assert "Setting up Plant Sensor integration entry" in caplog.text
            assert (
                "Plant Sensor integration setup completed successfully" in caplog.text
            )

    async def test_async_setup_entry_adds_update_listener(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that setup entry adds update listener."""
        mock_config_entry.add_update_listener = Mock()

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ):
            await async_setup_entry(hass, mock_config_entry)
            mock_config_entry.add_update_listener.assert_called_once()

    async def test_async_update_entry(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test config entry update handling."""
        with patch.object(hass.config_entries, "async_reload") as mock_reload:
            mock_reload.return_value = True

            await async_update_entry(hass, mock_config_entry)

            mock_reload.assert_called_once_with(mock_config_entry.entry_id)
            assert "Handling config entry update" in caplog.text
            assert "Config entry test_entry_id reloaded successfully" in caplog.text

    async def test_async_unload_entry_success(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test successful unloading of config entry."""
        # Set up hass data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = mock_config_entry.data

        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = True

            result = await async_unload_entry(hass, mock_config_entry)

            assert result is True
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]
            mock_unload.assert_called_once_with(mock_config_entry, ["sensor"])
            assert "Unloading Plant Sensor config entry" in caplog.text
            assert "Successfully unloaded config entry" in caplog.text

    async def test_async_unload_entry_no_data(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test unloading config entry with no existing data."""
        hass.data.setdefault(DOMAIN, {})

        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = True

            result = await async_unload_entry(hass, mock_config_entry)

            assert result is True
            assert "No entry data found to remove" in caplog.text

    async def test_async_unload_entry_failure(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test failed unloading of config entry."""
        hass.data.setdefault(DOMAIN, {})

        with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
            mock_unload.return_value = False

            result = await async_unload_entry(hass, mock_config_entry)

            assert result is False
            assert "Failed to unload config entry" in caplog.text

    async def test_async_remove_config_entry_device_success(
        self,
        hass: HomeAssistant,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test successful device removal from config entry."""
        # Create mock device entry
        device_entry = Mock(spec=DeviceEntry)
        device_entry.id = "test_device_id"
        device_entry.identifiers = {(DOMAIN, "test_plant_device")}

        # Create mock subentry
        mock_subentry = Mock()
        mock_subentry.data = {"device_id": "test_plant_device"}

        # Create mock config entry with subentries
        mock_config_entry = Mock(spec=ConfigEntry)
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.subentries = {"subentry_id": mock_subentry}

        with patch.object(
            hass.config_entries, "async_remove_subentry"
        ) as mock_remove_subentry:
            result = await async_remove_config_entry_device(
                hass, mock_config_entry, device_entry
            )

            assert result is True
            mock_remove_subentry.assert_called_once_with(
                mock_config_entry, "subentry_id"
            )
            assert (
                "Removed subentry subentry_id for device test_plant_device"
                in caplog.text
            )

    async def test_async_remove_config_entry_device_no_device_id(
        self,
        hass: HomeAssistant,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test device removal with no matching device ID in identifiers."""
        device_entry = Mock(spec=DeviceEntry)
        device_entry.id = "test_device_id"
        device_entry.identifiers = {("other_domain", "test_device")}

        mock_config_entry = Mock(spec=ConfigEntry)
        mock_config_entry.entry_id = "test_entry_id"

        result = await async_remove_config_entry_device(
            hass, mock_config_entry, device_entry
        )

        assert result is False
        assert "Could not find device ID in identifiers" in caplog.text

    async def test_async_remove_config_entry_device_no_matching_subentry(
        self,
        hass: HomeAssistant,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test device removal with no matching subentry."""
        device_entry = Mock(spec=DeviceEntry)
        device_entry.id = "test_device_id"
        device_entry.identifiers = {(DOMAIN, "test_plant_device")}

        # Mock subentry with different device_id
        mock_subentry = Mock()
        mock_subentry.data = {"device_id": "different_device"}

        mock_config_entry = Mock(spec=ConfigEntry)
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.subentries = {"subentry_id": mock_subentry}

        result = await async_remove_config_entry_device(
            hass, mock_config_entry, device_entry
        )

        assert result is False
        assert "Could not find subentry with device_id" in caplog.text
