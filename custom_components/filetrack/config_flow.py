import logging
import uuid
from homeassistant import config_entries
from homeassistant.helpers.storage import Store
from homeassistant.helpers import selector
import voluptuous as vol
from .const import (DOMAIN, CONF_FOLDER_PATHS, CONF_FILTER, CONF_SORT, CONF_RECURSIVE, DEFAULT_FILTER, DEFAULT_SORT, DEFAULT_RECURSIVE, SORT_OPTIONS)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.sensors"
_LOGGER = logging.getLogger(__name__)


class FileTrackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Auto-setup: geen formulier nodig, activeert FileTrack direct."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="FileTrack", data={})

    @staticmethod
    def async_get_options_flow(config_entry):
        return FileTrackOptionsFlow(config_entry)


class FileTrackOptionsFlow(config_entries.OptionsFlow):
    """Options flow. Updated menu with add/remove control based on modern entity linking"""

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._to_remove = []

    async def async_step_init(self, user_input=None):
        _LOGGER.debug("FileTrack: Options menu requested (async_step_init)")
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_sensor", "remove_sensor"]
        )

    async def async_step_add_sensor(self, user_input=None):
        errors = {}
        if user_input is not None:
            folder = user_input[CONF_FOLDER_PATHS]
            if not folder.startswith("/config/www/"):
                errors[CONF_FOLDER_PATHS] = "invalid_path"
            if not errors:
                _LOGGER.info("FileTrack: Adding new sensor: %s", user_input["name"])
                store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
                stored = await store.async_load() or {"sensors": []}
                new_sensor = {
                    "id": uuid.uuid4().hex,
                    "name": user_input["name"],
                    CONF_FOLDER_PATHS: user_input[CONF_FOLDER_PATHS],
                    CONF_FILTER: user_input.get(CONF_FILTER, DEFAULT_FILTER),
                    CONF_SORT: user_input.get(CONF_SORT, DEFAULT_SORT),
                    CONF_RECURSIVE: user_input.get(CONF_RECURSIVE, DEFAULT_RECURSIVE),
                }
            
                stored["sensors"].append(new_sensor)
                await store.async_save(stored)
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Required("name"): str,
            vol.Required(CONF_FOLDER_PATHS, default="/config/www/your-folder"): str,
            vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): str,
            vol.Optional(CONF_SORT, default=DEFAULT_SORT): vol.In(SORT_OPTIONS),
            vol.Optional(CONF_RECURSIVE, default=DEFAULT_RECURSIVE): bool,
        })
        
        return self.async_show_form(step_id="add_sensor", data_schema=data_schema, errors=errors)

    async def async_step_remove_sensor(self, user_input=None):
        _LOGGER.debug("FileTrack: Remove sensor step triggered")
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        stored = await store.async_load() or {"sensors": []}
        sensors = stored.get("sensors", [])
        errors = {}

        if not sensors:
            return self.async_abort(reason="no_sensors")
            
        if user_input is not None:
            self._to_remove = user_input.get("sensors", [])
            if self._to_remove:
                _LOGGER.info("FileTrack: User selected sensors for removal: %s", self._to_remove)
                return await self.async_step_confirm()
            errors["base"] = "no_selection"

        options = [{"value": s["id"], "label": f"{s['name']} ({s[CONF_FOLDER_PATHS]})"} for s in sensors]
        return self.async_show_form(
            step_id="remove_sensor",
            data_schema=vol.Schema({
                vol.Required("sensors", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, 
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST
                    )
                )
            }),
            errors=errors,
        )

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            if user_input.get("confirm"):
                for sensor_id in self._to_remove:
                    await self._do_remove(sensor_id)
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            return self.async_abort(reason="cancelled")

        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        stored = await store.async_load() or {"sensors": []}
        id_to_name = {s["id"]: f"{s['name']} ({s[CONF_FOLDER_PATHS]})" for s in stored.get("sensors", [])}
        names = "\n".join(f"• {id_to_name.get(i, i)}" for i in self._to_remove)
        
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): bool,
            }),
            description_placeholders={"names": names},
        )

    async def _do_remove(self, sensor_id):
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        stored = await store.async_load() or {"sensors": []}
        entity_id = None
        registry = None
        
        match = next((s for s in stored["sensors"] if s["id"] == sensor_id), None)
        if match:
            from homeassistant.helpers import entity_registry as er
            registry = er.async_get(self.hass)
            unique_id = f"filetrack_{sensor_id}"
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)

        # Remove from registry
        if entity_id and registry:
            registry.async_remove(entity_id)
            _LOGGER.debug("FileTrack: Removed entity %s from registry", entity_id)

        # Remove from storage
        before = len(stored["sensors"])
        stored["sensors"] = [s for s in stored["sensors"] if s["id"] != sensor_id]
        after = len(stored["sensors"])
        if before == after:
            _LOGGER.debug("FileTrack: Storage delete failed; sensor_id=%s not found", sensor_id)
        else:
            _LOGGER.debug("FileTrack: Removed sensor_id %s from storage", sensor_id)
        
        await store.async_save(stored)
        if before != after:
            name = match['name'] if match else sensor_id
            _LOGGER.info("FileTrack: Successfully removed sensor '%s'", name)

        return before != after
