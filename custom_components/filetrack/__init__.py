import os
import uuid
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from .const import DOMAIN, CONF_FOLDER_PATHS, CONF_FILTER, CONF_SORT, CONF_RECURSIVE, CONF_UNIQUE_ID, DEFAULT_FILTER, DEFAULT_SORT, DEFAULT_RECURSIVE, SORT_OPTIONS

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = f"{DOMAIN}.sensors"
STORAGE_VERSION = 1
MIGRATION_VERSION = 2

SENSOR_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required(CONF_FOLDER_PATHS): cv.string,
    vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
    vol.Optional(CONF_SORT, default=DEFAULT_SORT): vol.In(SORT_OPTIONS),
    vol.Optional(CONF_RECURSIVE, default=DEFAULT_RECURSIVE): cv.boolean,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional("sensors", default=[]): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
    })
}, extra=vol.ALLOW_EXTRA)

ADD_SENSOR_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required(CONF_FOLDER_PATHS): cv.string,
    vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
    vol.Optional(CONF_SORT, default=DEFAULT_SORT): cv.string,
    vol.Optional(CONF_RECURSIVE, default=DEFAULT_RECURSIVE): cv.boolean,
})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Verwerk YAML-configuratie onder het filetrack: domein."""
    hass.data.setdefault(DOMAIN, {})
    domain_config = config.get(DOMAIN, {})
    hass.data[DOMAIN]["yaml_sensors"] = domain_config.get("sensors", [])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Laad FileTrack vanuit het config entry en registreer de add_sensor service."""
    _LOGGER.debug("FileTrack: Starting async_setup_entry. Version: %s", entry.version)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load() or {"sensors": []}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["stored"] = stored
    hass.data[DOMAIN]["add_entities"] = None
    hass.data[DOMAIN].setdefault("yaml_sensors", [])

    # Check for old/unlinked sensors
    if entry.version < MIGRATION_VERSION:
        await async_migrate_filetrack_entities(hass)
        hass.config_entries.async_update_entry(
            entry,
            version=MIGRATION_VERSION,
        )
    
    # Create device in registry for proper linking
    from homeassistant.helpers import device_registry as dr
    from .const import MANUFACTURER, MODEL
    
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "filetrack_service_device")},
        name="FileTrack",
        manufacturer=MANUFACTURER,
        model=MODEL,
    )

    async def handle_add_sensor(call: ServiceCall) -> None:
        name = call.data["name"].strip()
        folder = call.data[CONF_FOLDER_PATHS].strip().rstrip("/")
        filter_term = call.data.get(CONF_FILTER, DEFAULT_FILTER)
        sort = call.data.get(CONF_SORT, DEFAULT_SORT)
        recursive = call.data.get(CONF_RECURSIVE, DEFAULT_RECURSIVE)

        def create_folder():
            if not os.path.isdir(folder):
                os.makedirs(folder, exist_ok=True)

        try:
            await hass.async_add_executor_job(create_folder)
        except Exception as e:
            _LOGGER.error("FileTrack: Failed to create folder %s: %s", folder, e)
            raise ValueError(f"Cannot create folder: {folder}") from e

        sensor_id = uuid.uuid4().hex
        sensor_config = {
            "id": sensor_id,
            "name": name,
            CONF_FOLDER_PATHS: folder,
            CONF_FILTER: filter_term,
            CONF_SORT: sort,
            CONF_RECURSIVE: recursive,
        }
        stored["sensors"].append(sensor_config)
        await store.async_save(stored)

        add_entities = hass.data[DOMAIN].get("add_entities")
        if add_entities:
            from .sensor import FileTrackSensor
            add_entities([FileTrackSensor(folder, name, filter_term, sort, recursive, f"filetrack_{sensor_id}", config_entry=entry)], True)
        else:
            _LOGGER.warning("FileTrack: sensor platform not loaded yet, sensor appears after restart")

    if not hass.services.has_service(DOMAIN, "add_sensor"):
        hass.services.async_register(DOMAIN, "add_sensor", handle_add_sensor, schema=ADD_SENSOR_SCHEMA)

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Satisfy Home Assistant core migration requirement."""
    return True
    

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_remove(DOMAIN, "add_sensor")
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])


async def async_migrate_filetrack_entities(hass):
    _LOGGER.info("FileTrack: First run. Checking sensors for v2 migration")
    registry = er.async_get(hass)
    migration_count = 0
    stored = hass.data.get(DOMAIN, {}).get("stored", {}).get("sensors", [])
    yaml_sensors = hass.data.get(DOMAIN, {}).get("yaml_sensors", [])
    yaml_by_name = {slugify(s["name"]): s for s in yaml_sensors}

    for entity in list(registry.entities.values()):
        if entity.domain != "sensor":
            continue
        if entity.platform != DOMAIN:
            continue
        if entity.unique_id:
            _LOGGER.info("FileTrack: Migration skipped %s (has unique_id %s)", entity.entity_id, entity.unique_id)
            continue

        object_id = entity.entity_id.split(".", 1)[1]
        new_unique_id = None

        # UI sensors
        for sensor in stored:
            expected_object_id = slugify(sensor["name"])
            if object_id == expected_object_id:
                new_unique_id = f"filetrack_{sensor['id']}"
                _LOGGER.debug("FileTrack: Migration found %s without unique_id. Assigned %s", entity.entity_id, new_unique_id)
                break

        # YAML sensors
        if new_unique_id is None and object_id in yaml_by_name:
            yaml_sensor = yaml_by_name[object_id]
            if yaml_sensor.get(CONF_UNIQUE_ID):
                new_unique_id = yaml_sensor[CONF_UNIQUE_ID]
                _LOGGER.debug("FileTrack: Migration found YAML %s with unique_id %s", entity.entity_id, new_unique_id)
            else:
                new_unique_id = f"{object_id}"
                _LOGGER.debug("FileTrack: Migration found YAML %s without unique_id. Assigned %s", entity.entity_id, new_unique_id)
        
        # Other sensors
        if new_unique_id is None:
            new_unique_id = f"filetrack_{object_id}"
            _LOGGER.debug("FileTrack: Migration found other %s without unique_id. Assigned %s", entity.entity_id, new_unique_id)
    
        # Migrate if matched
        if new_unique_id:
            try:
                registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
                _LOGGER.info("FileTrack: Migrated %s with unique_id %s", entity.entity_id, new_unique_id)
                migration_count += 1
            except Exception as err:
                _LOGGER.error("FileTrack: Failed migrating %s: %s", entity.entity_id, err)            

        else:
            _LOGGER.warning("FileTrack: Migration could not match entity %s (object_id: %s). Skipping.", entity.entity_id, object_id)

    if migration_count == 0:
        _LOGGER.info("FileTrack: Finished v2 migration. > No sensors need updating.")
    else:
        _LOGGER.info("FileTrack: Finished v2 migration. > %s sensors updated.", migration_count)
        
