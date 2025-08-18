"""Constants for the Plant Sensor integration."""

from homeassistant.util import slugify

DOMAIN = "openplantbook_ref"

# Image download constants
DEFAULT_IMAGE_PATH = "/config/www/images/plants/"
ATTR_IMAGE = "image_url"


def generate_device_id(plant_data: dict) -> str:
    """
    Generate a stable device ID from plant data.

    This creates a stable, user-friendly device identifier.
    For plants from OpenPlantBook, uses the plant_id.
    For manual entries, derives plant_id from scientific_name.
    Falls back to slugified name for legacy compatibility.
    """
    # First try to use plant_id if available
    plant_id = plant_data.get("plant_id")
    if plant_id:
        return slugify(plant_id)

    # For manual entries, try to derive from scientific_name
    scientific_name = plant_data.get("scientific_name")
    if scientific_name:
        return slugify(scientific_name)

    # Fall back to legacy plant name for backward compatibility
    plant_name = plant_data.get("name", "unnamed_plant")
    return slugify(plant_name)
