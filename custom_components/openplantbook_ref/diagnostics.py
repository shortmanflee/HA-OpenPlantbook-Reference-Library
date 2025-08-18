"""Diagnostics support for Plant Sensor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"client_id", "secret"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics_data = {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": entry.options,
        "entry_id": entry.entry_id,
        "entry_title": entry.title,
        "entry_unique_id": entry.unique_id,
        "subentries": {},
    }

    # Include subentry information (redacted)
    for subentry_id, subentry in entry.subentries.items():
        diagnostics_data["subentries"][subentry_id] = {
            "data": async_redact_data(subentry.data, TO_REDACT),
            "subentry_id": subentry.subentry_id,
        }

    # Include runtime data if available
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        runtime_data = hass.data[DOMAIN][entry.entry_id]
        diagnostics_data["runtime_data"] = async_redact_data(runtime_data, TO_REDACT)

    return diagnostics_data
