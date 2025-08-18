"""Config flow for Plant Sensor integration."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, SectionConfig, section
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import raise_if_invalid_filename, slugify

from .api import AsyncConfigEntryAuth
from .const import DOMAIN, HTTP_OK, generate_device_id

_LOGGER = logging.getLogger(__name__)


def _to_proper_case(text: str) -> str:
    """Convert text to proper case (title case) while handling special cases."""
    if not text or not text.strip():
        return text

    # Clean up the text
    text = text.strip()

    # Convert to title case
    return text.title()


def _get_existing_categories(hass: HomeAssistant) -> list[str]:
    """Get categories from existing plant entities."""
    existing_categories = set()

    # Get all config entries for this integration
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Check all subentries for categories
        for subentry in entry.subentries.values():
            categories = subentry.data.get("categories")
            if categories:
                if isinstance(categories, list):
                    existing_categories.update(categories)
                elif isinstance(categories, str):
                    # Handle old comma-separated format
                    existing_categories.update(
                        cat.strip() for cat in categories.split(",") if cat.strip()
                    )

    # Convert to sorted list, removing empty strings
    return sorted(cat for cat in existing_categories if cat and cat.strip())


def _get_categories_options(
    hass: HomeAssistant, additional_categories: list[str] | str | None = None
) -> list[str]:
    """
    Get list of categories from existing plants for dropdown options.

    Args:
        hass: Home Assistant instance
        additional_categories: Extra categories to include (e.g., from OpenPlantBook)

    """
    existing_categories = set(_get_existing_categories(hass))

    # Add any additional categories (e.g., from OpenPlantBook)
    if additional_categories:
        if isinstance(additional_categories, list):
            existing_categories.update(additional_categories)
        elif isinstance(additional_categories, str):
            # Handle comma-separated string format
            existing_categories.update(
                cat.strip() for cat in additional_categories.split(",") if cat.strip()
            )

    return sorted(existing_categories)


OPENPLANTBOOK_AVAILABLE = importlib.util.find_spec("openplantbook_sdk") is not None


class PlantSensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plant Sensor."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the PlantSensorConfigFlow."""
        self._data: dict | None = None

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """
        Show the setup form to the user and handle API credentials input.

        Note: Plant devices/entities are only created via subentry flows
        (PlantSubentryFlowHandler), not in this main config flow.
        This config entry only stores API credentials.
        """
        _LOGGER.debug(
            "Main config flow async_step_user called with input: %s",
            user_input is not None,
        )
        errors = {}
        api_credentials_schema = vol.Schema(
            {
                vol.Required("client_id"): str,
                vol.Required("secret"): str,
            }
        )

        # Pre-populate with existing data if in reauth flow
        default_client_id = ""
        if self.source == SOURCE_REAUTH:
            _LOGGER.info("Reauth flow detected in main config flow")
            entry = self._get_reauth_entry()
            default_client_id = entry.data.get("client_id", "")
            _LOGGER.debug("Using existing client_id for reauth: %s", default_client_id)
            api_credentials_schema = vol.Schema(
                {
                    vol.Required("client_id", default=default_client_id): str,
                    vol.Required("secret"): str,
                }
            )

        if user_input is not None:
            client_id = user_input.get("client_id", "").strip()
            secret = user_input.get("secret", "").strip()
            _LOGGER.debug(
                "Validating API credentials - client_id provided: %s", bool(client_id)
            )

            if not client_id:
                _LOGGER.warning("Client ID is required but not provided")
                errors["base"] = "client_id_required"
            if not secret:
                _LOGGER.warning("Secret is required but not provided")
                errors["base"] = "secret_required"
            if not errors:
                # Test connection before proceeding
                _LOGGER.info("Testing API connection with provided credentials")
                try:
                    auth = AsyncConfigEntryAuth(client_id, secret)
                    # Try to get the API client to validate credentials are working
                    await auth.get_api_client()
                    _LOGGER.info("API credentials validated successfully")
                except ConfigEntryAuthFailed:
                    _LOGGER.exception(
                        "API credentials validation failed - invalid authentication"
                    )
                    errors["base"] = "invalid_auth"
                except Exception:  # Config flows should be robust
                    _LOGGER.exception(
                        "API credentials validation failed - connection error"
                    )
                    errors["base"] = "cannot_connect"

                if errors:
                    _LOGGER.debug("Showing form again due to validation errors")
                    return self.async_show_form(
                        step_id="user",
                        data_schema=api_credentials_schema,
                        errors=errors,
                        description_placeholders={},
                    )

                if self.source == SOURCE_REAUTH:
                    # For reauth, we keep the existing unique ID and just update
                    # credentials
                    _LOGGER.info("Updating existing entry with new credentials")
                    entry = self._get_reauth_entry()
                    # Ensure we're updating the same entry by using its existing
                    # unique_id
                    await self.async_set_unique_id(entry.unique_id)
                    self._abort_if_unique_id_mismatch()
                    # Update the existing entry with new credentials
                    updated_data = {
                        **entry.data,
                        "client_id": client_id,
                        "secret": secret,
                    }
                    _LOGGER.info(
                        "Reauth completed successfully for entry %s", entry.entry_id
                    )
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=updated_data,
                    )

                # For initial setup, use client_id as unique ID for the config entry
                _LOGGER.info("Setting up new integration entry")
                await self.async_set_unique_id(client_id)
                self._abort_if_unique_id_configured()

                # Store the API credentials for later use
                self._data = {"client_id": client_id, "secret": secret}
                # Go directly to image config - plants are added via subentries only
                _LOGGER.debug("Proceeding to image configuration step")
                return await self.async_step_image_config()

        _LOGGER.debug("Showing initial API credentials form")
        return self.async_show_form(
            step_id="user",
            data_schema=api_credentials_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_image_config(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure image download options."""
        errors = {}

        if user_input is not None:
            download_images = user_input.get("download_images", False)
            download_path = user_input.get("download_path", "www/images/plants/")

            # Validate download path if image download is enabled
            if download_images:
                path_obj = Path(download_path)
                if not path_obj.is_absolute():
                    path_obj = Path(self.hass.config.path(download_path))

                # Check if directory exists or can be created
                try:
                    path_obj.mkdir(parents=True, exist_ok=True)
                except OSError:
                    errors["download_path"] = "invalid_path"

            if not errors:
                # Store image config with API credentials
                config_data = {
                    **self._data,
                    "download_images": download_images,
                    "download_path": download_path,
                }

                return self.async_create_entry(
                    title="Open PlantBook",
                    data=config_data,
                )

        # Create schema for image configuration
        image_config_schema = vol.Schema(
            {
                vol.Optional("download_images", default=False): bool,
                vol.Optional("download_path", default="www/images/plants/"): str,
            }
        )

        return self.async_show_form(
            step_id="image_config",
            data_schema=image_config_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, _config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"plant": PlantSubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()


class PlantSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a plant."""

    def __init__(self) -> None:
        """Initialize the PlantSubentryFlowHandler."""
        _LOGGER.debug("Initializing PlantSubentryFlowHandler")
        self._plant_search_results: list[dict] = []
        self._selected_plant: dict | None = None
        self._plant_name: str | None = None

    def _is_reauth_flow_in_progress(self, entry_id: str) -> bool:
        """Check if a reauth flow is already in progress for the given config entry."""
        in_progress_flows = self.hass.config_entries.flow.async_progress()
        for flow in in_progress_flows:
            if (
                flow["context"].get("source") == SOURCE_REAUTH
                and flow["context"].get("entry_id") == entry_id
            ):
                _LOGGER.debug(
                    "Reauth flow already in progress for entry %s, flow_id: %s",
                    entry_id,
                    flow["flow_id"],
                )
                return True
        return False

    async def async_download_image(self, url: str, download_to: str) -> str | bool:
        """Download image from URL to specified path."""
        _LOGGER.debug("Going to download image %s to %s", url, download_to)

        path_obj = Path(download_to)
        if path_obj.exists():
            _LOGGER.warning(
                "File %s already exists. Will not download again", download_to
            )
            return download_to

        websession = async_get_clientsession(self.hass)

        try:
            async with asyncio.timeout(10):
                _LOGGER.debug("Requesting URL: %s", url)
                resp = await websession.get(url)
                _LOGGER.debug("Response status: %d", resp.status)
                if resp.status != HTTP_OK:
                    _LOGGER.warning(
                        "Downloading '%s' failed, status_code=%d", url, resp.status
                    )
                    return False

                data = await resp.read()
                _LOGGER.debug("Downloaded %d bytes", len(data))

            # Ensure directory exists
            _LOGGER.debug("Creating directory: %s", path_obj.parent)
            path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Write the file using executor for blocking I/O
            _LOGGER.debug("Writing file: %s", path_obj)
            await self.hass.async_add_executor_job(path_obj.write_bytes, data)

            _LOGGER.debug("Downloading of %s done", url)
            return str(path_obj)

        except (TimeoutError, OSError):
            _LOGGER.exception("Failed to download image %s", url)
            return False

    async def _handle_plant_image_download(
        self, device_data: dict, device_id: str
    ) -> None:
        """Handle plant image download and set entity picture."""
        _LOGGER.debug("_handle_plant_image_download called for device %s", device_id)

        if not self._selected_plant:
            _LOGGER.debug("No selected plant, skipping image download")
            return

        _LOGGER.debug("Selected plant data keys: %s", list(self._selected_plant.keys()))

        # Check for different possible image field names
        image_url = None
        for field_name in [
            "image_url",
            "image",
            "image_path",
            "img_url",
            "photo_url",
            "picture_url",
        ]:
            if self._selected_plant.get(field_name):
                image_url = self._selected_plant[field_name]
                _LOGGER.debug(
                    "Found image URL in field '%s': %s", field_name, image_url
                )
                break

        if not image_url:
            _LOGGER.debug("No image URL found in plant data, skipping image download")
            return

        parent_entry = self._get_entry()
        _LOGGER.debug("Parent entry data: %s", parent_entry.data)
        _LOGGER.debug(
            "download_images setting: %s", parent_entry.data.get("download_images")
        )

        # Default to True if download_images setting is missing
        # (for backward compatibility)
        download_images = parent_entry.data.get("download_images", True)
        if not download_images:
            _LOGGER.debug("Image download disabled in config, skipping")
            return

        _LOGGER.debug("Starting image download process")
        _LOGGER.debug("Image URL: %s", image_url)

        filename = (
            slugify(
                urllib.parse.unquote(Path(image_url).name),
                separator=" ",
            )
            .replace(" jpg", ".jpg")
            .replace(" png", ".png")
        )

        # Validate filename
        try:
            raise_if_invalid_filename(filename)
        except ValueError:
            filename = f"plant_{device_id}.jpg"  # Fallback filename

        _LOGGER.debug("Generated filename: %s", filename)

        # Prepare download path
        download_path = parent_entry.data.get("download_path", "www/images/plants/")

        # Handle legacy absolute paths by converting them to relative paths
        if download_path == "/config/www/images/plants/":
            download_path = "www/images/plants/"

        path_obj = Path(download_path)
        if not path_obj.is_absolute():
            path_obj = Path(self.hass.config.path(download_path))

        final_path = path_obj / filename
        _LOGGER.debug("Final download path: %s", final_path)

        # Download the image
        downloaded_file = await self.async_download_image(image_url, str(final_path))
        _LOGGER.debug("Downloaded file result: %s", downloaded_file)

        if downloaded_file and "www/" in str(downloaded_file):
            # Convert local path to web-accessible path
            local_url = re.sub(r"^.*www/", "/local/", str(downloaded_file))
            device_data["entity_picture"] = local_url
            _LOGGER.debug(
                "Set entity picture to %s for device %s", local_url, device_id
            )
        else:
            _LOGGER.warning(
                "Failed to download image or path doesn't contain 'www/': %s",
                downloaded_file,
            )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step where user enters plant name for search."""
        _LOGGER.debug(
            "Subentry flow async_step_user called with input: %s",
            user_input is not None,
        )
        errors = {}

        # Check if reauthentication is required upfront
        parent_entry = self._get_entry()
        _LOGGER.debug(
            "Checking reauth status for parent entry: %s", parent_entry.entry_id
        )
        if self._is_reauth_flow_in_progress(parent_entry.entry_id):
            _LOGGER.warning("Aborting subentry flow - reauth required for parent entry")
            return self.async_abort(reason="reauth_required")

        if user_input is not None:
            plant_name = user_input.get("plant_name", "").strip()
            _LOGGER.debug("Plant name entered: %s", plant_name)
            if not plant_name:
                _LOGGER.warning("Plant name is required but not provided")
                errors["base"] = "plant_name_required"
            else:
                # Store the plant name and initiate search
                self._plant_name = plant_name
                _LOGGER.info("Starting plant search for: %s", plant_name)
                return await self.async_step_search_plants()

        # Show form to enter plant name for search
        # Prepopulate with existing plant name if available
        default_plant_name = self._plant_name or ""
        _LOGGER.debug("Showing plant name form with default: %s", default_plant_name)
        plant_search_schema = vol.Schema(
            {
                vol.Required("plant_name", default=default_plant_name): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=plant_search_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_search_plants(
        self, _user_input: dict | None = None
    ) -> FlowResult:
        """Search for plants using openplantbook-sdk."""
        _LOGGER.info("Starting plant search for: %s", self._plant_name)

        if not OPENPLANTBOOK_AVAILABLE:
            _LOGGER.error("OpenPlantBook SDK is not available")
            return self.async_abort(reason="missing_dependency")

        # Get API credentials from parent config entry
        parent_entry = self._get_entry()
        client_id = parent_entry.data.get("client_id")
        secret = parent_entry.data.get("secret")
        _LOGGER.debug(
            "Retrieved API credentials from parent entry %s", parent_entry.entry_id
        )

        if not client_id or not secret:
            _LOGGER.error("No API credentials found in parent config entry")
            return self.async_abort(reason="missing_api_credentials")

        try:
            # Use our API wrapper with authentication error handling
            auth = AsyncConfigEntryAuth(client_id, secret)
            _LOGGER.debug("Making API search request for plant: %s", self._plant_name)
            search_results = await auth.async_plant_search(self._plant_name)

            # Handle the API response structure - search results might be nested
            results_list = search_results
            if isinstance(search_results, dict):
                _LOGGER.debug("Search results is dict, looking for nested results")
                # If the API returns a dict, look for common keys that might
                # contain results
                if "results" in search_results:
                    results_list = search_results["results"]
                    _LOGGER.debug(
                        "Found results in 'results' key: %d items", len(results_list)
                    )
                elif "data" in search_results:
                    results_list = search_results["data"]
                    _LOGGER.debug(
                        "Found results in 'data' key: %d items", len(results_list)
                    )
                elif "plants" in search_results:
                    results_list = search_results["plants"]
                    _LOGGER.debug(
                        "Found results in 'plants' key: %d items", len(results_list)
                    )
                else:
                    # If it's a dict but doesn't have expected keys, treat as
                    # single result
                    results_list = [search_results]
                    _LOGGER.debug("Treating dict as single result")

            if not results_list:
                # No results found - offer manual entry option
                _LOGGER.info("No search results found for plant: %s", self._plant_name)
                return await self.async_step_no_results_found()

            if len(results_list) == 1:
                # Exactly one result - use it directly
                _LOGGER.info("Found single search result for: %s", self._plant_name)
                self._selected_plant = results_list[0]
                return await self.async_step_configure_plant()

            # Multiple results - show selection list
            _LOGGER.info(
                "Found %d search results for: %s", len(results_list), self._plant_name
            )
            self._plant_search_results = results_list
            return await self.async_step_select_plant()

        except ConfigEntryAuthFailed:
            _LOGGER.exception(
                "Authentication failed during plant search for '%s'",
                self._plant_name,
            )
            # Trigger reauth flow on the parent entry only if one isn't already
            # in progress
            parent_entry = self._get_entry()
            if not self._is_reauth_flow_in_progress(parent_entry.entry_id):
                _LOGGER.info(
                    "Initiating reauth flow for parent entry: %s", parent_entry.entry_id
                )
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={
                            "source": SOURCE_REAUTH,
                            "entry_id": parent_entry.entry_id,
                        },
                        data=parent_entry.data,
                    )
                )
            else:
                _LOGGER.debug("Reauth flow already in progress, not starting new one")
            return self.async_abort(reason="reauth_required")
        except (ImportError, AttributeError, ConnectionError, TimeoutError):
            _LOGGER.exception(
                "Connection/import error during plant search for '%s'",
                self._plant_name,
            )
            # Return to search step with error and preserve the plant name
            errors = {"base": "search_error"}
            plant_search_schema = vol.Schema(
                {
                    vol.Required("plant_name", default=self._plant_name or ""): str,
                }
            )
            return self.async_show_form(
                step_id="user",
                data_schema=plant_search_schema,
                errors=errors,
                description_placeholders={"error": "Connection error"},
            )
        except Exception as err:
            # Handle any other unexpected errors including aiohttp exceptions
            _LOGGER.exception(
                "Unexpected error searching for plants '%s'", self._plant_name
            )
            _LOGGER.debug("Full error details", exc_info=True)
            errors = {"base": "search_error"}
            plant_search_schema = vol.Schema(
                {
                    vol.Required("plant_name", default=self._plant_name or ""): str,
                }
            )
            return self.async_show_form(
                step_id="user",
                data_schema=plant_search_schema,
                errors=errors,
                description_placeholders={"error": str(err)},
            )

    async def async_step_no_results_found(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle case when no plants are found in search."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "manual_entry":
                self._selected_plant = None  # Clear any selected plant
                return await self.async_step_configure_plant()
            if action == "search_again":
                # Go back to the user step to search again
                return await self.async_step_user()

        # Show options to user when no results found
        no_results_schema = vol.Schema(
            {
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "manual_entry", "label": "manual_entry"},
                            {"value": "search_again", "label": "search_again"},
                        ],
                        translation_key="action",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="no_results_found",
            data_schema=no_results_schema,
            errors={},
            description_placeholders={"plant_name": self._plant_name},
        )

    async def async_step_select_plant(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle plant selection when multiple plants are found."""
        errors = {}

        if user_input is not None:
            selected_pid = user_input.get("selected_plant")
            if selected_pid == "manual_entry":
                # User chose manual entry
                self._selected_plant = None  # Clear any selected plant
                return await self.async_step_configure_plant()
            if selected_pid == "search_again":
                # User wants to search again
                return await self.async_step_user()
            if selected_pid:
                # Find the selected plant in our results
                self._selected_plant = next(
                    (
                        plant
                        for plant in self._plant_search_results
                        if plant.get("pid") == selected_pid
                    ),
                    None,
                )
                if self._selected_plant:
                    return await self.async_step_configure_plant()

                errors["base"] = "invalid_selection"
            else:
                errors["base"] = "no_plant_selected"

        # Create selection options from search results
        plant_options = [
            {
                "value": plant.get("pid", ""),
                "label": (
                    f"{plant.get('display_pid', plant.get('alias', 'Unknown'))} "
                    f"({plant.get('category', '')})"
                ),
            }
            for plant in self._plant_search_results
        ]

        # Add manual entry and search again options
        plant_options.extend(
            [
                {"value": "manual_entry", "label": "manual_entry"},
                {"value": "search_again", "label": "search_again"},
            ]
        )

        plant_selection_schema = vol.Schema(
            {
                vol.Required("selected_plant"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=plant_options,
                        translation_key="selected_plant",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_plant",
            data_schema=plant_selection_schema,
            errors=errors,
            description_placeholders={"count": str(len(self._plant_search_results))},
        )

    async def async_step_configure_plant(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure the selected plant with all details."""
        # If we just selected a plant, fetch its detailed information
        if self._selected_plant and "min_light_lux" not in self._selected_plant:
            await self._fetch_plant_details()

        if user_input is not None:
            errors = await self._validate_plant_configuration(user_input)
            if not errors:
                return await self._create_plant_entry(user_input)
        else:
            errors = {}

        return self._show_plant_configuration_form(errors)

    async def _validate_plant_configuration(self, user_input: dict) -> dict[str, str]:
        """Validate plant configuration input."""
        errors = {}

        # Extract values from sections
        plant_data = self._extract_plant_data(user_input)

        # Validate required fields
        errors.update(self._validate_required_fields(plant_data))

        # Validate min/max pairs if no errors so far
        if not errors:
            errors.update(self._validate_min_max_pairs(plant_data))

        return errors

    def _extract_plant_data(self, user_input: dict) -> dict:
        """Extract and format plant data from user input."""
        names_section = user_input.get("names_section", {})
        categories_section = user_input.get("categories_section", {})
        light_section = user_input.get("light_values_section", {})
        temp_section = user_input.get("temperature_values_section", {})
        humidity_section = user_input.get("humidity_values_section", {})
        moisture_section = user_input.get("moisture_values_section", {})
        soil_ec_section = user_input.get("soil_ec_values_section", {})

        return {
            "friendly_name": _to_proper_case(names_section.get("friendly_name", "")),
            "scientific_name": _to_proper_case(
                names_section.get("scientific_name", "")
            ),
            "common_name": _to_proper_case(names_section.get("common_name", "")),
            "categories": [
                _to_proper_case(cat) for cat in categories_section.get("categories", [])
            ],
            "min_light": light_section.get("min_light"),
            "max_light": light_section.get("max_light"),
            "min_temp": temp_section.get("min_temp"),
            "max_temp": temp_section.get("max_temp"),
            "min_humidity": humidity_section.get("min_humidity"),
            "max_humidity": humidity_section.get("max_humidity"),
            "min_moisture": moisture_section.get("min_moisture"),
            "max_moisture": moisture_section.get("max_moisture"),
            "min_soil_ec": soil_ec_section.get("min_soil_ec"),
            "max_soil_ec": soil_ec_section.get("max_soil_ec"),
        }

    def _validate_required_fields(self, plant_data: dict) -> dict[str, str]:
        """Validate required fields."""
        errors = {}

        if not plant_data["friendly_name"]:
            errors["names_section"] = "friendly_name_required"
        elif not plant_data["scientific_name"]:
            errors["names_section"] = "scientific_name_required"
        elif not plant_data["common_name"]:
            errors["names_section"] = "common_name_required"
        elif not plant_data["categories"]:
            errors["categories_section"] = "categories_required"
        elif plant_data["min_light"] is None:
            errors["light_values_section"] = "min_light_required"
        elif plant_data["max_light"] is None:
            errors["light_values_section"] = "max_light_required"
        elif plant_data["min_temp"] is None:
            errors["temperature_values_section"] = "min_temp_required"
        elif plant_data["max_temp"] is None:
            errors["temperature_values_section"] = "max_temp_required"
        elif plant_data["min_humidity"] is None:
            errors["humidity_values_section"] = "min_humidity_required"
        elif plant_data["max_humidity"] is None:
            errors["humidity_values_section"] = "max_humidity_required"
        elif plant_data["min_moisture"] is None:
            errors["moisture_values_section"] = "min_moisture_required"
        elif plant_data["max_moisture"] is None:
            errors["moisture_values_section"] = "max_moisture_required"
        elif plant_data["min_soil_ec"] is None:
            errors["soil_ec_values_section"] = "min_soil_ec_required"
        elif plant_data["max_soil_ec"] is None:
            errors["soil_ec_values_section"] = "max_soil_ec_required"

        return errors

    def _validate_min_max_pairs(self, plant_data: dict) -> dict[str, str]:
        """Validate min/max value pairs."""
        errors = {}

        validation_pairs = [
            (
                plant_data["min_light"],
                plant_data["max_light"],
                "light",
                "light_values_section",
            ),
            (
                plant_data["min_temp"],
                plant_data["max_temp"],
                "temperature",
                "temperature_values_section",
            ),
            (
                plant_data["min_humidity"],
                plant_data["max_humidity"],
                "humidity",
                "humidity_values_section",
            ),
            (
                plant_data["min_moisture"],
                plant_data["max_moisture"],
                "moisture",
                "moisture_values_section",
            ),
            (
                plant_data["min_soil_ec"],
                plant_data["max_soil_ec"],
                "soil_ec",
                "soil_ec_values_section",
            ),
        ]

        for min_val, max_val, field_type, section_key in validation_pairs:
            if min_val is not None and max_val is not None:
                if min_val > max_val:
                    errors[section_key] = f"min_greater_than_max_{field_type}"
                    break
                if min_val == max_val:
                    errors[section_key] = f"min_equals_max_{field_type}"
                    break

        return errors

    async def _create_plant_entry(self, user_input: dict) -> FlowResult:
        """Create the plant configuration entry."""
        plant_data = self._extract_plant_data(user_input)

        # Determine plant_id and device_name
        plant_id = (
            self._selected_plant.get("pid")
            if self._selected_plant
            else plant_data["scientific_name"]
        )
        device_name = plant_data["friendly_name"] or plant_data["scientific_name"]

        # Generate device data and ID
        device_data_for_id = {
            "plant_id": plant_id,
            "scientific_name": plant_data["scientific_name"],
            "name": device_name,
            **{k: v for k, v in plant_data.items() if k.startswith(("min_", "max_"))},
        }
        device_id = generate_device_id(device_data_for_id)

        # Prepare complete device data
        device_data = {
            "name": device_name,
            "plant_id": plant_id,
            "scientific_name": plant_data["scientific_name"],
            "common_name": plant_data["common_name"] or None,
            "categories": plant_data["categories"] or None,
            "friendly_name": plant_data["friendly_name"] or None,
            **{k: v for k, v in plant_data.items() if k.startswith(("min_", "max_"))},
        }

        # Add plant book data if available
        if self._selected_plant:
            device_data["plant_book_data"] = self._selected_plant

        # Handle image download
        await self._handle_plant_image_download(device_data, device_id)

        # Create entry
        _LOGGER.debug(
            "Creating subentry with title: %s and device_id: %s",
            device_data.get("name", "Plant Device"),
            device_id,
        )
        return self.async_create_entry(
            title=device_data.get("scientific_name", "Plant Device"),
            data={"device_id": device_id, **device_data},
            unique_id=device_id,
        )

    def _show_plant_configuration_form(self, errors: dict[str, str]) -> FlowResult:
        """Show the plant configuration form with current data."""
        # Pre-populate fields from selected plant if available
        defaults = self._get_form_defaults()
        schema = self._create_configuration_schema(defaults)

        return self.async_show_form(
            step_id="configure_plant",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "plant_name": self._selected_plant.get("display_pid", "Unknown")
                if self._selected_plant
                else (self._plant_name or "Unknown")
            },
        )

    def _get_form_defaults(self) -> dict:
        """Get default values for the form fields."""
        defaults = {
            "friendly_name": "",
            "scientific_name": "",
            "common_name": "",
            "categories": [],
            "min_light": None,
            "max_light": None,
            "min_temp": None,
            "max_temp": None,
            "min_humidity": None,
            "max_humidity": None,
            "min_moisture": None,
            "max_moisture": None,
            "min_soil_ec": None,
            "max_soil_ec": None,
        }

        if self._selected_plant:
            # Extract plant identification data and apply proper case formatting
            defaults["scientific_name"] = _to_proper_case(
                self._selected_plant.get(
                    "display_pid", self._selected_plant.get("alias", "")
                )
            )
            defaults["common_name"] = _to_proper_case(
                self._selected_plant.get(
                    "alias", self._selected_plant.get("common_name", "")
                )
            )

            # Set friendly name to common name from OpenPlantBook, or scientific
            # name as fallback
            defaults["friendly_name"] = (
                defaults["scientific_name"] or defaults["common_name"]
            )

            # Handle categories
            categories_data = self._selected_plant.get("category", [])
            if isinstance(categories_data, str):
                defaults["categories"] = [
                    _to_proper_case(cat.strip())
                    for cat in categories_data.split(",")
                    if cat.strip()
                ]
            elif isinstance(categories_data, list):
                defaults["categories"] = [
                    _to_proper_case(cat) for cat in categories_data if cat
                ]

            # Extract plant parameters from detail data
            param_mapping = {
                "min_light": "min_light_lux",
                "max_light": "max_light_lux",
                "min_temp": "min_temp",
                "max_temp": "max_temp",
                "min_humidity": "min_env_humid",
                "max_humidity": "max_env_humid",
                "min_moisture": "min_soil_moist",
                "max_moisture": "max_soil_moist",
                "min_soil_ec": "min_soil_ec",
                "max_soil_ec": "max_soil_ec",
            }

            for default_key, plant_key in param_mapping.items():
                if plant_key in self._selected_plant:
                    defaults[default_key] = self._selected_plant[plant_key]
        else:
            # For manual entry, use the stored plant name
            plant_name = _to_proper_case(self._plant_name or "")
            defaults["scientific_name"] = plant_name
            defaults["friendly_name"] = plant_name

        return defaults

    def _create_configuration_schema(self, defaults: dict) -> vol.Schema:
        """Create the configuration schema with default values."""
        # Include OpenPlantBook categories in dropdown options if available
        opb_categories = defaults["categories"] if self._selected_plant else None
        categories_options = _get_categories_options(self.hass, opb_categories)

        return vol.Schema(
            {
                # Names section
                vol.Optional("names_section"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "friendly_name", default=defaults["friendly_name"]
                            ): selector.TextSelector(
                                selector.TextSelectorConfig(
                                    type=selector.TextSelectorType.TEXT
                                )
                            ),
                            vol.Required(
                                "scientific_name", default=defaults["scientific_name"]
                            ): selector.TextSelector(
                                selector.TextSelectorConfig(
                                    type=selector.TextSelectorType.TEXT
                                )
                            ),
                            vol.Required(
                                "common_name", default=defaults["common_name"]
                            ): selector.TextSelector(
                                selector.TextSelectorConfig(
                                    type=selector.TextSelectorType.TEXT
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": False}),
                ),
                # Categories section
                vol.Optional("categories_section"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "categories", default=defaults["categories"]
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=categories_options,
                                    multiple=True,
                                    custom_value=True,
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": False}),
                ),
                # Light values section
                vol.Optional(
                    "light_values_section",
                    default={
                        "min_light": defaults["min_light"],
                        "max_light": defaults["max_light"],
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_light", default=defaults["min_light"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    unit_of_measurement="lux",
                                )
                            ),
                            vol.Required(
                                "max_light", default=defaults["max_light"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    unit_of_measurement="lux",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Temperature values section
                vol.Optional(
                    "temperature_values_section",
                    default={
                        "min_temp": defaults["min_temp"],
                        "max_temp": defaults["max_temp"],
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_temp", default=defaults["min_temp"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    step=0.1,
                                    unit_of_measurement="°C",
                                )
                            ),
                            vol.Required(
                                "max_temp", default=defaults["max_temp"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    step=0.1,
                                    unit_of_measurement="°C",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Humidity values section
                vol.Optional(
                    "humidity_values_section",
                    default={
                        "min_humidity": defaults["min_humidity"],
                        "max_humidity": defaults["max_humidity"],
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_humidity", default=defaults["min_humidity"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                            vol.Required(
                                "max_humidity", default=defaults["max_humidity"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Moisture values section
                vol.Optional(
                    "moisture_values_section",
                    default={
                        "min_moisture": defaults["min_moisture"],
                        "max_moisture": defaults["max_moisture"],
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_moisture", default=defaults["min_moisture"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                            vol.Required(
                                "max_moisture", default=defaults["max_moisture"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Soil EC values section
                vol.Optional(
                    "soil_ec_values_section",
                    default={
                        "min_soil_ec": defaults["min_soil_ec"],
                        "max_soil_ec": defaults["max_soil_ec"],
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_soil_ec", default=defaults["min_soil_ec"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    step=0.01,
                                    unit_of_measurement="mS/cm",
                                )
                            ),
                            vol.Required(
                                "max_soil_ec", default=defaults["max_soil_ec"]
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    step=0.01,
                                    unit_of_measurement="mS/cm",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
            }
        )

    async def _fetch_plant_details(self) -> None:
        """Fetch detailed plant information using the plant ID."""
        if not self._selected_plant or not OPENPLANTBOOK_AVAILABLE:
            _LOGGER.debug(
                "Cannot fetch plant details - selected_plant: %s, SDK available: %s",
                bool(self._selected_plant),
                OPENPLANTBOOK_AVAILABLE,
            )
            return

        plant_id = self._selected_plant.get("pid")
        if not plant_id:
            _LOGGER.debug("No plant ID available for detail lookup")
            return

        _LOGGER.debug("Fetching details for plant ID: %s", plant_id)

        try:
            # Get API credentials from parent config entry
            parent_entry = self._get_entry()
            client_id = parent_entry.data.get("client_id")
            secret = parent_entry.data.get("secret")

            if not client_id or not secret:
                _LOGGER.warning("No API credentials available for plant detail lookup")
                return

            # Use our API wrapper with authentication error handling
            auth = AsyncConfigEntryAuth(client_id, secret)
            plant_details = await auth.async_plant_detail_get(plant_id)

            if plant_details:
                _LOGGER.debug("Plant details received: %s", plant_details)
                _LOGGER.debug("Plant details keys: %s", list(plant_details.keys()))

                # Update the selected plant with detailed information
                self._selected_plant.update(plant_details)
                _LOGGER.debug(
                    "Updated selected plant data keys: %s",
                    list(self._selected_plant.keys()),
                )
                _LOGGER.debug("Fetched plant details for %s", plant_id)
            else:
                _LOGGER.warning("No plant details returned for %s", plant_id)

        except ConfigEntryAuthFailed as err:
            _LOGGER.warning(
                "Authentication failed during plant detail fetch for %s: %s",
                plant_id,
                err,
            )
            # Trigger reauth flow on the parent entry only if one isn't already
            # in progress
            parent_entry = self._get_entry()
            if not self._is_reauth_flow_in_progress(parent_entry.entry_id):
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={
                            "source": SOURCE_REAUTH,
                            "entry_id": parent_entry.entry_id,
                        },
                        data=parent_entry.data,
                    )
                )
        except (ConnectionError, TimeoutError, ImportError, AttributeError) as err:
            _LOGGER.warning("Failed to fetch plant details for %s: %s", plant_id, err)

    async def async_step_reconfigure(
        self, _user_input: dict | None = None
    ) -> FlowResult:
        """Handle reconfiguration of a plant subentry."""
        return await self.async_step_configure_plant_options()

    async def async_step_configure_plant_options(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure plant min/max values through subentry options."""
        if self.source not in ("reconfigure", "user"):
            return self.async_abort(reason="invalid_source")

        # Only check for reauth flow when not in reconfigure mode
        # Reconfigure operations should proceed independently of reauth status
        if self.source != "reconfigure":
            parent_entry = self._get_entry()
            if self._is_reauth_flow_in_progress(parent_entry.entry_id):
                return self.async_abort(reason="reauth_required")

        # Get current plant data from subentry
        if self.source == "reconfigure":
            subentry = self._get_reconfigure_subentry()
            current_data = subentry.data.copy()
            plant_name = current_data.get("name", "Plant")
        else:
            # This shouldn't happen for plant subentries, but handle gracefully
            return self.async_abort(reason="invalid_source")

        if user_input is not None:
            return await self._handle_configure_plant_options_input(
                user_input, current_data, subentry
            )

        # Create schema with current values as defaults
        configure_schema = self._create_configure_plant_options_schema(current_data)

        return self.async_show_form(
            step_id="configure_plant_options",
            data_schema=configure_schema,
            errors={},
            description_placeholders={"plant_name": plant_name},
        )

    async def _handle_configure_plant_options_input(
        self,
        user_input: dict,
        current_data: dict,
        subentry: config_entries.ConfigSubentry,
    ) -> FlowResult:
        """Handle user input for configure plant options."""
        # Extract values from sections
        section_data = self._extract_section_data(user_input)

        # Validate input
        errors = self._validate_configure_plant_options_input(section_data)

        if errors:
            configure_schema = self._create_configure_plant_options_schema(current_data)
            return self.async_show_form(
                step_id="configure_plant_options",
                data_schema=configure_schema,
                errors=errors,
                description_placeholders={
                    "plant_name": current_data.get("name", "Plant")
                },
            )

        # Create updated data
        updated_data = self._create_updated_plant_data(section_data, current_data)

        return self.async_update_and_abort(
            self._get_entry(),
            subentry,
            data=updated_data,
        )

    def _extract_section_data(self, user_input: dict) -> dict:
        """Extract and format data from user input sections."""
        names_section = user_input.get("names_section", {})
        categories_section = user_input.get("categories_section", {})
        light_section = user_input.get("light_values_section", {})
        temp_section = user_input.get("temperature_values_section", {})
        humidity_section = user_input.get("humidity_values_section", {})
        moisture_section = user_input.get("moisture_values_section", {})
        soil_ec_section = user_input.get("soil_ec_values_section", {})

        return {
            "friendly_name": _to_proper_case(names_section.get("friendly_name", "")),
            "scientific_name": _to_proper_case(
                names_section.get("scientific_name", "")
            ),
            "common_name": _to_proper_case(names_section.get("common_name", "")),
            "categories": [
                _to_proper_case(cat) for cat in categories_section.get("categories", [])
            ],
            "light_section": light_section,
            "temp_section": temp_section,
            "humidity_section": humidity_section,
            "moisture_section": moisture_section,
            "soil_ec_section": soil_ec_section,
        }

    def _validate_configure_plant_options_input(
        self, section_data: dict
    ) -> dict[str, str]:
        """Validate configure plant options input."""
        errors = {}

        # Validate required fields first
        errors.update(self._validate_required_plant_fields(section_data))

        if not errors:
            # Validate min/max pairs
            errors.update(self._validate_plant_min_max_pairs(section_data))

        return errors

    def _validate_required_plant_fields(self, section_data: dict) -> dict[str, str]:
        """Validate required plant fields."""
        errors = {}

        if not section_data["friendly_name"]:
            errors["names_section"] = "friendly_name_required"
            return errors
        if not section_data["scientific_name"]:
            errors["names_section"] = "scientific_name_required"
            return errors
        if not section_data["common_name"]:
            errors["names_section"] = "common_name_required"
            return errors
        if not section_data["categories"]:
            errors["categories_section"] = "categories_required"
            return errors

        # Validate numeric fields
        numeric_validations = [
            (
                section_data["light_section"].get("min_light"),
                "light_values_section",
                "min_light_required",
            ),
            (
                section_data["light_section"].get("max_light"),
                "light_values_section",
                "max_light_required",
            ),
            (
                section_data["temp_section"].get("min_temp"),
                "temperature_values_section",
                "min_temp_required",
            ),
            (
                section_data["temp_section"].get("max_temp"),
                "temperature_values_section",
                "max_temp_required",
            ),
            (
                section_data["humidity_section"].get("min_humidity"),
                "humidity_values_section",
                "min_humidity_required",
            ),
            (
                section_data["humidity_section"].get("max_humidity"),
                "humidity_values_section",
                "max_humidity_required",
            ),
            (
                section_data["moisture_section"].get("min_moisture"),
                "moisture_values_section",
                "min_moisture_required",
            ),
            (
                section_data["moisture_section"].get("max_moisture"),
                "moisture_values_section",
                "max_moisture_required",
            ),
            (
                section_data["soil_ec_section"].get("min_soil_ec"),
                "soil_ec_values_section",
                "min_soil_ec_required",
            ),
            (
                section_data["soil_ec_section"].get("max_soil_ec"),
                "soil_ec_values_section",
                "max_soil_ec_required",
            ),
        ]

        for value, section_key, error_key in numeric_validations:
            if value is None:
                errors[section_key] = error_key
                return errors

        return errors

    def _validate_plant_min_max_pairs(self, section_data: dict) -> dict[str, str]:
        """Validate min/max value pairs for plant configuration."""
        errors = {}

        validation_pairs = [
            (
                section_data["light_section"].get("min_light"),
                section_data["light_section"].get("max_light"),
                "light",
                "light_values_section",
            ),
            (
                section_data["temp_section"].get("min_temp"),
                section_data["temp_section"].get("max_temp"),
                "temperature",
                "temperature_values_section",
            ),
            (
                section_data["humidity_section"].get("min_humidity"),
                section_data["humidity_section"].get("max_humidity"),
                "humidity",
                "humidity_values_section",
            ),
            (
                section_data["moisture_section"].get("min_moisture"),
                section_data["moisture_section"].get("max_moisture"),
                "moisture",
                "moisture_values_section",
            ),
            (
                section_data["soil_ec_section"].get("min_soil_ec"),
                section_data["soil_ec_section"].get("max_soil_ec"),
                "soil_ec",
                "soil_ec_values_section",
            ),
        ]

        for min_val, max_val, field_type, section_key in validation_pairs:
            if min_val is not None and max_val is not None:
                if min_val > max_val:
                    errors[section_key] = f"min_greater_than_max_{field_type}"
                    break
                if min_val == max_val:
                    errors[section_key] = f"min_equals_max_{field_type}"
                    break

        return errors

    def _create_updated_plant_data(
        self, section_data: dict, current_data: dict
    ) -> dict:
        """Create updated plant data from section data and current data."""
        categories_list = (
            section_data["categories"] if section_data["categories"] else []
        )

        # Determine plant_id (preserve existing or derive from scientific_name)
        plant_id = current_data.get("plant_id")
        if not plant_id:
            plant_id = section_data["scientific_name"]

        # Determine device name - friendly_name takes precedence
        device_name = (
            section_data["friendly_name"]
            if section_data["friendly_name"]
            else section_data["scientific_name"]
        )

        return {
            **current_data,
            "name": device_name,
            "plant_id": plant_id,
            "scientific_name": section_data["scientific_name"],
            "common_name": section_data["common_name"]
            if section_data["common_name"]
            else None,
            "categories": categories_list if categories_list else None,
            "friendly_name": section_data["friendly_name"]
            if section_data["friendly_name"]
            else None,
            "min_light": section_data["light_section"].get("min_light"),
            "max_light": section_data["light_section"].get("max_light"),
            "min_temp": section_data["temp_section"].get("min_temp"),
            "max_temp": section_data["temp_section"].get("max_temp"),
            "min_humidity": section_data["humidity_section"].get("min_humidity"),
            "max_humidity": section_data["humidity_section"].get("max_humidity"),
            "min_moisture": section_data["moisture_section"].get("min_moisture"),
            "max_moisture": section_data["moisture_section"].get("max_moisture"),
            "min_soil_ec": section_data["soil_ec_section"].get("min_soil_ec"),
            "max_soil_ec": section_data["soil_ec_section"].get("max_soil_ec"),
        }

    def _create_configure_plant_options_schema(self, current_data: dict) -> vol.Schema:
        """Create schema for configure plant options form."""
        current_categories = self._prepare_current_categories(current_data)
        plant_book_data = current_data.get("plant_book_data", {})

        # Create helper function to get default value, preferring current data
        # over OpenPlantbook data
        def get_default_value(
            current_key: str, plantbook_key: str | None = None
        ) -> Any:
            """Get default value from current data or OpenPlantbook data."""
            current_value = current_data.get(current_key)
            if current_value is not None:
                return current_value
            if plantbook_key and plant_book_data:
                return plant_book_data.get(plantbook_key)
            return None

        return vol.Schema(
            {
                # Names section
                vol.Optional("names_section"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "friendly_name",
                                default=_to_proper_case(
                                    current_data.get(
                                        "friendly_name", current_data.get("name", "")
                                    )
                                ),
                            ): selector.TextSelector(
                                selector.TextSelectorConfig(
                                    type=selector.TextSelectorType.TEXT
                                )
                            ),
                            vol.Required(
                                "scientific_name",
                                default=_to_proper_case(
                                    current_data.get("scientific_name", "")
                                ),
                            ): selector.TextSelector(
                                selector.TextSelectorConfig(
                                    type=selector.TextSelectorType.TEXT
                                )
                            ),
                            vol.Required(
                                "common_name",
                                default=_to_proper_case(
                                    current_data.get("common_name", "")
                                ),
                            ): selector.TextSelector(
                                selector.TextSelectorConfig(
                                    type=selector.TextSelectorType.TEXT
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": False}),
                ),
                # Categories section
                vol.Optional("categories_section"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "categories", default=current_categories
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=_get_categories_options(
                                        self.hass, current_categories
                                    ),
                                    multiple=True,
                                    custom_value=True,
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": False}),
                ),
                # Light values section
                vol.Optional(
                    "light_values_section",
                    default={
                        "min_light": get_default_value("min_light", "min_light_lux"),
                        "max_light": get_default_value("max_light", "max_light_lux"),
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_light",
                                default=get_default_value("min_light", "min_light_lux"),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    unit_of_measurement="lux",
                                )
                            ),
                            vol.Required(
                                "max_light",
                                default=get_default_value("max_light", "max_light_lux"),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    unit_of_measurement="lux",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Temperature values section
                vol.Optional(
                    "temperature_values_section",
                    default={
                        "min_temp": get_default_value("min_temp", "min_temp"),
                        "max_temp": get_default_value("max_temp", "max_temp"),
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_temp",
                                default=get_default_value("min_temp", "min_temp"),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    step=0.1,
                                    unit_of_measurement="°C",
                                )
                            ),
                            vol.Required(
                                "max_temp",
                                default=get_default_value("max_temp", "max_temp"),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    step=0.1,
                                    unit_of_measurement="°C",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Humidity values section
                vol.Optional(
                    "humidity_values_section",
                    default={
                        "min_humidity": get_default_value(
                            "min_humidity", "min_env_humid"
                        ),
                        "max_humidity": get_default_value(
                            "max_humidity", "max_env_humid"
                        ),
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_humidity",
                                default=get_default_value(
                                    "min_humidity", "min_env_humid"
                                ),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                            vol.Required(
                                "max_humidity",
                                default=get_default_value(
                                    "max_humidity", "max_env_humid"
                                ),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Moisture values section
                vol.Optional(
                    "moisture_values_section",
                    default={
                        "min_moisture": get_default_value(
                            "min_moisture", "min_soil_moist"
                        ),
                        "max_moisture": get_default_value(
                            "max_moisture", "max_soil_moist"
                        ),
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_moisture",
                                default=get_default_value(
                                    "min_moisture", "min_soil_moist"
                                ),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                            vol.Required(
                                "max_moisture",
                                default=get_default_value(
                                    "max_moisture", "max_soil_moist"
                                ),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    unit_of_measurement="%",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
                # Soil EC values section
                vol.Optional(
                    "soil_ec_values_section",
                    default={
                        "min_soil_ec": get_default_value("min_soil_ec", "min_soil_ec"),
                        "max_soil_ec": get_default_value("max_soil_ec", "max_soil_ec"),
                    },
                ): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "min_soil_ec",
                                default=get_default_value("min_soil_ec", "min_soil_ec"),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    step=0.01,
                                    unit_of_measurement="mS/cm",
                                )
                            ),
                            vol.Required(
                                "max_soil_ec",
                                default=get_default_value("max_soil_ec", "max_soil_ec"),
                            ): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    step=0.01,
                                    unit_of_measurement="mS/cm",
                                )
                            ),
                        }
                    ),
                    SectionConfig({"collapsed": True}),
                ),
            }
        )

    def _prepare_current_categories(self, current_data: dict) -> list[str]:
        """Prepare current categories list for form display."""
        current_categories = current_data.get("categories", [])

        # Ensure categories is a list for the multi-select component and apply
        # proper case formatting
        if isinstance(current_categories, str):
            # Convert string to list by splitting on commas (for backward
            # compatibility) and apply proper case
            return [
                _to_proper_case(cat.strip())
                for cat in current_categories.split(",")
                if cat.strip()
            ]
        if isinstance(current_categories, list):
            # Apply proper case formatting to existing list items
            return [_to_proper_case(cat) for cat in current_categories if cat]

        return []


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Plant Sensor integration."""

    def _is_reauth_flow_in_progress(self, entry_id: str) -> bool:
        """Check if a reauth flow is already in progress for the given config entry."""
        flows = self.hass.config_entries.flow.async_progress()
        return any(
            flow.get("handler") == DOMAIN
            and flow.get("context", {}).get("source") == SOURCE_REAUTH
            and flow.get("context", {}).get("entry_id") == entry_id
            for flow in flows
        )

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Configure image download settings."""
        # Check if reauthentication is required upfront
        if self._is_reauth_flow_in_progress(self.config_entry.entry_id):
            return self.async_abort(reason="reauth_required")

        errors = {}

        if user_input is not None:
            download_images = user_input.get("download_images", False)
            download_path = user_input.get("download_path", "www/images/plants/")

            # Validate download path if image download is enabled
            if download_images:
                path_obj = Path(download_path)
                if not path_obj.is_absolute():
                    path_obj = Path(self.hass.config.path(download_path))

                # Check if directory exists or can be created
                try:
                    path_obj.mkdir(parents=True, exist_ok=True)
                except OSError:
                    errors["download_path"] = "invalid_path"

            if not errors:
                # Update config entry data with new image settings
                new_data = {
                    **self.config_entry.data,
                    "download_images": download_images,
                    "download_path": download_path,
                }

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

                return self.async_create_entry(title="", data={})

        # Get current settings
        current_download_images = self.config_entry.data.get("download_images", True)
        current_download_path = self.config_entry.data.get(
            "download_path", "www/images/plants/"
        )

        # Create schema for image settings
        options_schema = vol.Schema(
            {
                vol.Optional("download_images", default=current_download_images): bool,
                vol.Optional("download_path", default=current_download_path): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )
