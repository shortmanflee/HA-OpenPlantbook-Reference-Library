"""API wrapper for OpenPlantBook with authentication error handling."""

from __future__ import annotations

import importlib.util
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed

if TYPE_CHECKING:
    if importlib.util.find_spec("openplantbook_sdk"):
        from openplantbook_sdk import OpenPlantBookApi
    else:
        OpenPlantBookApi = object

_LOGGER = logging.getLogger(__name__)

OPENPLANTBOOK_AVAILABLE = importlib.util.find_spec("openplantbook_sdk") is not None


# Define authentication-related exceptions that can occur with the OpenPlantBook API
class OpenPlantBookAuthError(Exception):
    """Base exception for OpenPlantBook authentication errors."""


class OpenPlantBookInvalidCredentialsError(OpenPlantBookAuthError):
    """Exception for invalid API credentials."""


class OpenPlantBookTokenExpiredError(OpenPlantBookAuthError):
    """Exception for expired API tokens."""


class AsyncConfigEntryAuth:
    """Authentication wrapper for OpenPlantBook API."""

    def __init__(self, client_id: str, secret: str) -> None:
        """Initialize the auth wrapper."""
        _LOGGER.debug("Initializing AsyncConfigEntryAuth with client_id: %s", client_id)
        self.client_id = client_id
        self.secret = secret
        self._api = None

    async def get_api_client(self) -> Any:  # type: ignore[misc]
        """Get or create the API client."""
        if self._api is None:
            _LOGGER.debug("Creating new OpenPlantBook API client")
            if not OPENPLANTBOOK_AVAILABLE:
                _LOGGER.error(
                    "OpenPlantBook SDK not available - cannot create API client"
                )
                msg = "OpenPlantBook SDK not available"
                raise ConfigEntryAuthFailed(msg)
            # Import here to handle optional dependency
            from openplantbook_sdk import OpenPlantBookApi  # noqa: PLC0415

            try:
                self._api = OpenPlantBookApi(self.client_id, self.secret)
                _LOGGER.info("OpenPlantBook API client created successfully")
            except Exception:
                _LOGGER.exception("Failed to create OpenPlantBook API client")
                raise
        else:
            _LOGGER.debug("Reusing existing OpenPlantBook API client")
        return self._api

    async def async_plant_search(self, plant_name: str) -> Any:  # type: ignore[misc]
        """Search for plants with authentication error handling."""
        _LOGGER.info("Searching for plant: %s", plant_name)
        api = await self.get_api_client()
        try:
            _LOGGER.debug("Making API call to search for plant: %s", plant_name)
            result = await api.async_plant_search(plant_name)
        except Exception as err:
            _LOGGER.debug(
                "API call failed with exception: %s (type: %s)", err, type(err).__name__
            )
            # Check if this is an authentication error
            if self._is_auth_error(err):
                _LOGGER.warning(
                    "Authentication error detected during plant search for '%s': %s",
                    plant_name,
                    err,
                )
                msg = f"Authentication failed: {err}"
                raise ConfigEntryAuthFailed(msg) from err
            _LOGGER.exception(
                "Non-authentication error during plant search for '%s'",
                plant_name,
            )
            raise
        else:
            _LOGGER.info("Plant search completed successfully for: %s", plant_name)
            _LOGGER.debug("Search result type: %s", type(result).__name__)
            if isinstance(result, list):
                _LOGGER.debug("Found %d search results", len(result))
            elif isinstance(result, dict) and "results" in result:
                _LOGGER.debug("Found %d search results", len(result["results"]))
            return result

    async def async_plant_detail_get(self, plant_id: str) -> dict[str, Any]:
        """Get plant details with authentication error handling."""
        _LOGGER.info("Getting plant details for ID: %s", plant_id)
        api = await self.get_api_client()
        try:
            _LOGGER.debug("Making API call to get plant details for ID: %s", plant_id)
            result = await api.async_plant_detail_get(plant_id)
        except Exception as err:
            _LOGGER.debug(
                "API call failed with exception: %s (type: %s)", err, type(err).__name__
            )
            # Check if this is an authentication error
            if self._is_auth_error(err):
                _LOGGER.warning(
                    "Authentication error detected during plant detail fetch "
                    "for ID '%s': %s",
                    plant_id,
                    err,
                )
                msg = f"Authentication failed: {err}"
                raise ConfigEntryAuthFailed(msg) from err
            _LOGGER.exception(
                "Non-authentication error during plant detail fetch for ID '%s'",
                plant_id,
            )
            raise
        else:
            _LOGGER.info("Plant details retrieved successfully for ID: %s", plant_id)
            _LOGGER.debug("Plant details result type: %s", type(result).__name__)
            return result

    def _is_auth_error(self, exception: Exception) -> bool:
        """Check if an exception indicates an authentication error."""
        _LOGGER.debug("Checking if exception is an authentication error: %s", exception)

        # Check for specific exception types that indicate auth errors
        if isinstance(exception, PermissionError):
            _LOGGER.debug("Exception is PermissionError - treating as auth error")
            return True

        # Convert exception to string to check for common auth error patterns
        error_str = str(exception).lower()
        _LOGGER.debug("Exception string (lowercase): %s", error_str)

        # Common authentication error indicators
        auth_indicators = [
            "unauthorized",
            "authentication",
            "invalid credentials",
            "access denied",
            "forbidden",
            "401",
            "403",
            "invalid api key",
            "invalid client",
            "token expired",
            "authentication failed",
            "wrong client id",
            "wrong secret",
            "no plantbook token",
            "permission denied",
            # OpenPlantBook SDK specific error messages
            "wrong client id or secret",
            "no token available",
            "token not found",
            "invalid token",
            "expired token",
        ]

        for indicator in auth_indicators:
            if indicator in error_str:
                _LOGGER.debug("Found auth error indicator: %s", indicator)
                return True

        _LOGGER.debug("No authentication error indicators found")
        return False
