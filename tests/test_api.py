"""Test the API module of the Open Plantbook Reference Library integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.openplantbook_ref.api import AsyncConfigEntryAuth


class TestAsyncConfigEntryAuth:
    """Test the AsyncConfigEntryAuth class."""

    def test_init(self) -> None:
        """Test AsyncConfigEntryAuth initialization."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")
        assert auth.client_id == "test_client_id"
        assert auth.secret == "test_secret"
        assert auth._api is None

    async def test_get_api_client_success(self) -> None:
        """Test successful API client creation."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        with patch(
            "custom_components.openplantbook_ref.api.OPENPLANTBOOK_AVAILABLE", True
        ):
            with patch("openplantbook_sdk.OpenPlantBookApi") as mock_api_class:
                mock_api_instance = Mock()
                mock_api_class.return_value = mock_api_instance

                result = await auth.get_api_client()

                assert result is mock_api_instance
                assert auth._api is mock_api_instance
                mock_api_class.assert_called_once_with("test_client_id", "test_secret")

    async def test_get_api_client_reuse_existing(self) -> None:
        """Test reusing existing API client."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")
        mock_api = Mock()
        auth._api = mock_api

        result = await auth.get_api_client()

        assert result is mock_api

    async def test_get_api_client_sdk_not_available(self) -> None:
        """Test API client creation when SDK is not available."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        with patch(
            "custom_components.openplantbook_ref.api.OPENPLANTBOOK_AVAILABLE", False
        ):
            with pytest.raises(
                ConfigEntryAuthFailed, match="OpenPlantBook SDK not available"
            ):
                await auth.get_api_client()

    async def test_get_api_client_creation_error(self) -> None:
        """Test API client creation error handling."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        with patch(
            "custom_components.openplantbook_ref.api.OPENPLANTBOOK_AVAILABLE", True
        ):
            with patch("openplantbook_sdk.OpenPlantBookApi") as mock_api_class:
                mock_api_class.side_effect = Exception("Creation failed")

                with pytest.raises(Exception, match="Creation failed"):
                    await auth.get_api_client()

    async def test_async_plant_search_success(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test successful plant search."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        mock_api = AsyncMock()
        mock_result = {"results": [{"pid": "test_plant", "alias": "Test Plant"}]}
        mock_api.async_plant_search.return_value = mock_result
        auth._api = mock_api

        result = await auth.async_plant_search("test plant")

        assert result == mock_result
        mock_api.async_plant_search.assert_called_once_with("test plant")
        assert "Searching for plant: test plant" in caplog.text
        assert "Plant search completed successfully" in caplog.text

    async def test_async_plant_search_auth_error(self) -> None:
        """Test plant search with authentication error."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        mock_api = AsyncMock()
        mock_api.async_plant_search.side_effect = PermissionError("Unauthorized")
        auth._api = mock_api

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await auth.async_plant_search("test plant")

    async def test_async_plant_search_non_auth_error(self) -> None:
        """Test plant search with non-authentication error."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        mock_api = AsyncMock()
        mock_api.async_plant_search.side_effect = ValueError("Invalid input")
        auth._api = mock_api

        with pytest.raises(ValueError, match="Invalid input"):
            await auth.async_plant_search("test plant")

    async def test_async_plant_detail_get_success(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test successful plant detail retrieval."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        mock_api = AsyncMock()
        mock_result = {"pid": "test_plant_123", "alias": "Test Plant", "max_temp": 25}
        mock_api.async_plant_detail_get.return_value = mock_result
        auth._api = mock_api

        result = await auth.async_plant_detail_get("test_plant_123")

        assert result == mock_result
        mock_api.async_plant_detail_get.assert_called_once_with("test_plant_123")
        assert "Getting plant details for ID: test_plant_123" in caplog.text
        assert "Plant details retrieved successfully" in caplog.text

    async def test_async_plant_detail_get_auth_error(self) -> None:
        """Test plant detail retrieval with authentication error."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        mock_api = AsyncMock()
        mock_api.async_plant_detail_get.side_effect = PermissionError("Access denied")
        auth._api = mock_api

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await auth.async_plant_detail_get("test_plant_123")

    async def test_async_plant_detail_get_non_auth_error(self) -> None:
        """Test plant detail retrieval with non-authentication error."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        mock_api = AsyncMock()
        mock_api.async_plant_detail_get.side_effect = ValueError("Invalid plant ID")
        auth._api = mock_api

        with pytest.raises(ValueError, match="Invalid plant ID"):
            await auth.async_plant_detail_get("test_plant_123")

    def test_is_auth_error_permission_error(self) -> None:
        """Test _is_auth_error with PermissionError."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        result = auth._is_auth_error(PermissionError("Access denied"))

        assert result is True

    @pytest.mark.parametrize(
        "error_message",
        [
            "unauthorized access",
            "authentication failed",
            "invalid credentials",
            "access denied",
            "forbidden request",
            "401 error",
            "403 forbidden",
            "invalid api key",
            "invalid client",
            "token expired",
            "wrong client id",
            "wrong secret",
            "no plantbook token",
            "permission denied",
            "wrong client id or secret",
            "no token available",
            "token not found",
            "invalid token",
            "expired token",
        ],
    )
    def test_is_auth_error_various_indicators(self, error_message: str) -> None:
        """Test _is_auth_error with various authentication error indicators."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        result = auth._is_auth_error(Exception(error_message))

        assert result is True

    def test_is_auth_error_non_auth_error(self) -> None:
        """Test _is_auth_error with non-authentication error."""
        auth = AsyncConfigEntryAuth("test_client_id", "test_secret")

        result = auth._is_auth_error(ValueError("Invalid input format"))

        assert result is False
