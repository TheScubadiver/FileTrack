import glob
import os
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from .const import DOMAIN, CONF_FOLDER_PATHS, CONF_FILTER, CONF_SORT, CONF_RECURSIVE, CONF_UNIQUE_ID, DEFAULT_FILTER, DEFAULT_SORT, DEFAULT_RECURSIVE, SORT_OPTIONS

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required("name"): cv.string,
    vol.Required(CONF_FOLDER_PATHS): cv.string,
    vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
    vol.Optional(CONF_SORT, default=DEFAULT_SORT): vol.In(SORT_OPTIONS),
    vol.Optional(CONF_RECURSIVE, default=DEFAULT_RECURSIVE): cv.boolean,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
})


def get_files_list(folder_path, filter_term, sort, recursive):
    query = os.path.join(folder_path, filter_term)
    files = glob.glob(query, recursive=recursive)
    if sort == "name":
        return sorted(files)
    elif sort == "size":
        return sorted(files, key=os.path.getsize)
    else:  # date
        return sorted(files, key=os.path.getmtime, reverse=True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Sensor aanmaken via YAML configuratie (filetrack: sensors:)."""
    cfg = discovery_info if discovery_info is not None else config
    name = cfg["name"]
    entry_id = cfg.get(CONF_UNIQUE_ID)
    if entry_id is None:
        entry_id = f"yaml_{name.lower().replace(' ', '_')}"
    
    sensor = FileTrackSensor(
        folder_path=cfg[CONF_FOLDER_PATHS],
        name=name,
        filter_term=cfg.get(CONF_FILTER, DEFAULT_FILTER),
        sort=cfg.get(CONF_SORT, DEFAULT_SORT),
        recursive=cfg.get(CONF_RECURSIVE, DEFAULT_RECURSIVE),
        entry_id=entry_id,
    )
    async_add_entities([sensor], True)


async def async_setup_entry(hass, entry, async_add_entities):
    """Laad sensoren vanuit de opgeslagen configuratie."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["add_entities"] = async_add_entities

    stored = hass.data[DOMAIN].get("stored", {})
    entities = []
    for sc in stored.get("sensors", []):
        entities.append(FileTrackSensor(
            sc[CONF_FOLDER_PATHS],
            sc["name"],
            sc.get(CONF_FILTER, DEFAULT_FILTER),
            sc.get(CONF_SORT, DEFAULT_SORT),
            sc.get(CONF_RECURSIVE, DEFAULT_RECURSIVE),
            sc["id"]
        ))
    if entities:
        async_add_entities(entities, True)


class FileTrackSensor(SensorEntity):
    """De sensor definitie."""
    _attr_icon = "mdi:folder"
    _attr_native_unit_of_measurement = "MB"

    def __init__(self, folder_path, name, filter_term, sort, recursive, entry_id):
        self._attr_name = name
        self._attr_unique_id = f"filetrack_{entry_id}"
        self._folder_path = os.path.join(folder_path, "")
        self._filter_term = filter_term
        self._sort = sort
        self._recursive = recursive
        self._state = 0
        self._attributes = {}

    def update(self):
        """Haal de nieuwe data op."""
        files_list = get_files_list(self._folder_path, self._filter_term, self._sort, self._recursive)
        total_size = sum(os.path.getsize(f) for f in files_list if os.path.isfile(f))

        self._state = round(total_size / 1e6, 2)
        self._attributes = {
            "path": self._folder_path,
            "filter": self._filter_term,
            "number_of_files": len(files_list),
            "fileList": files_list,
            "sort": self._sort,
        }

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes
