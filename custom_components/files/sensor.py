"""FileTrack: Custom sensor for Home Assistant, forked for use with Camera Gallery Card."""

import glob
import logging
import os
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__ + ".filetrack")

CONF_FOLDER_PATHS = "folder"
CONF_FILTER = "filter"
CONF_NAME = "name"
CONF_SORT = "sort"
CONF_RECURSIVE = "recursive"
DEFAULT_FILTER = "*"
DEFAULT_SORT = "date"
DEFAULT_RECURSIVE = False

DOMAIN = "filetrack"

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FOLDER_PATHS): cv.isdir,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
        vol.Optional(CONF_SORT, default=DEFAULT_SORT): cv.string,
        vol.Optional(CONF_RECURSIVE, default=DEFAULT_RECURSIVE): cv.boolean,
    }
)


def get_files_list(folder_path: str, filter_term: str, sort: str, recursive: bool) -> list[str]:
    """Return the list of files in folder_path filtered and sorted according to parameters."""
    query = os.path.join(folder_path, filter_term)
    files = glob.glob(query, recursive=recursive)
    if sort == "name":
        return sorted(files)
    elif sort == "size":
        return sorted(files, key=os.path.getsize)
    else:  # default to 'date'
        return sorted(files, key=os.path.getmtime)


def get_size(files_list: list[str]) -> int:
    """Return the total size in bytes of files in the list."""
    return sum(os.stat(f).st_size for f in files_list if os.path.isfile(f))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the FileTrack sensor."""
    path = config.get(CONF_FOLDER_PATHS)
    name = config.get(CONF_NAME)

    if not hass.config.is_allowed_path(path):
        _LOGGER.error(
            "Folder %s is not valid or allowed. Ensure it is under /config/www/", path
        )
    else:
        sensor = FileTrackSensor(
            path,
            name,
            config.get(CONF_FILTER),
            config.get(CONF_SORT),
            config.get(CONF_RECURSIVE),
        )
        add_entities([sensor], True)


class FileTrackSensor(Entity):
    """Representation of a folder as a Home Assistant sensor."""

    ICON = "mdi:folder"

    def __init__(self, folder_path: str, name: str, filter_term: str, sort: str, recursive: bool):
        """Initialize the FileTrack sensor."""
        folder_path = os.path.join(folder_path, "")  # Ensure trailing slash
        self._folder_path = folder_path
        self._filter_term = filter_term
        self._number_of_files = 0
        self._size = 0
        self._name = name
        self._unit_of_measurement = "MB"
        self._sort = sort
        self._recursive = recursive
        self.fileList = []

    def update(self):
        """Update the sensor state."""
        files_list = get_files_list(
            self._folder_path, self._filter_term, self._sort, self._recursive
        )
        self.fileList = files_list
        self._number_of_files = len(files_list)
        self._size = get_size(files_list)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> float:
        """Return the state of the sensor in MB."""
        return round(self._size / 1e6, 2)

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return self.ICON

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        return {
            "path": self._folder_path,
            "filter": self._filter_term,
            "number_of_files": self._number_of_files,
            "bytes": self._size,
            "fileList": self.fileList,
            "sort": self._sort,
            "recursive": self._recursive,
        }

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement
