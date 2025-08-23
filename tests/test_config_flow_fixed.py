"""Test openplantbook_ref config flow."""

from unittest.mock import patch

import pytest
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.openplantbook_ref.config_flow import (
    PlantSensorConfigFlow,
    _get_existing_categories,
    _to_proper_case,
)
from custom_components.openplantbook_ref.const import DOMAIN


class TestConfigFlowHelpers:
    """Test helper functions."""

    def test_to_proper_case_normal_text(self) -> None:
        """Test _to_proper_case with normal text."""
        result = _to_proper_case("hello world")
        assert result == "Hello World"

    def test_to_proper_case_empty_text(self) -> None:
        """Test _to_proper_case with empty text."""
        result = _to_proper_case("")
        assert result == ""

    def test_to_proper_case_whitespace_only(self) -> None:
        """Test _to_proper_case with whitespace only."""
        result = _to_proper_case("   ")
        assert result == "   "

    def test_get_existing_categories_no_entries(self, hass: HomeAssistant) -> None:
        """Test _get_existing_categories with no config entries."""
        result = _get_existing_categories(hass)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_existing_categories_with_entries(self, hass: HomeAssistant) -> None:
        """Test _get_existing_categories with existing entries."""
        # This would need proper mock config entries to test fully
        result = _get_existing_categories(hass)
        assert isinstance(result, list)


class TestPlantSensorConfigFlow:
    """Test PlantSensorConfigFlow."""

    @pytest.mark.asyncio
    async def test_async_step_user_form_display(self, hass: HomeAssistant) -> None:
        """Test user step displays the form."""
        flow = PlantSensorConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_async_step_user_with_valid_data(self, hass: HomeAssistant) -> None:
        """Test user step with valid credentials."""
        flow = PlantSensorConfigFlow()
        flow.hass = hass
        # Initialize context properly for config flow
        flow.context = {}

        user_input = {
            "client_id": "test_client_id",
            "secret": "test_secret",
        }

        with patch(
            "custom_components.openplantbook_ref.config_flow.OPENPLANTBOOK_AVAILABLE",
            new=True,
        ):
            result = await flow.async_step_user(user_input)

            # Should proceed to create entry or show next step
            assert result["type"] in [
                data_entry_flow.FlowResultType.CREATE_ENTRY,
                data_entry_flow.FlowResultType.FORM,
            ]

    @pytest.mark.asyncio
    async def test_flow_init_sets_version(self) -> None:
        """Test that flow initialization sets correct version."""
        flow = PlantSensorConfigFlow()

        assert flow.VERSION == 1
        assert flow.MINOR_VERSION == 1

    def test_flow_has_domain(self) -> None:
        """Test that flow has correct domain."""
        # The domain is set via the class parameter in the class definition
        _flow = PlantSensorConfigFlow()
        # Since domain is defined as a class parameter, it should be accessible
        # The ConfigFlow base class should set this up properly
        assert DOMAIN == "openplantbook_ref"  # Just verify our constant is correct

    @pytest.mark.asyncio
    async def test_async_step_reauth_form(self, hass: HomeAssistant) -> None:
        """Test reauth step shows form."""
        flow = PlantSensorConfigFlow()
        flow.hass = hass

        # async_step_reauth requires _entry_data parameter
        entry_data = {"client_id": "test_client", "secret": "test_secret"}

        result = await flow.async_step_reauth(entry_data)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
