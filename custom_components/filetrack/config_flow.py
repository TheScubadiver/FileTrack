from homeassistant import config_entries
from homeassistant.helpers.storage import Store
from homeassistant.helpers import selector
import voluptuous as vol
from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.sensors"


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
    """Opties flow: sensoren verwijderen."""

    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._to_remove = []

    async def async_step_init(self, user_input=None):
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        stored = await store.async_load() or {"sensors": []}
        sensors = stored.get("sensors", [])

        if not sensors:
            return self.async_abort(reason="no_sensors")

        if user_input is not None:
            selected = user_input.get("sensors", [])
            if selected:
                self._to_remove = selected
                return await self.async_step_confirm()
            return self.async_abort(reason="cancelled")

        options = [{"value": s["name"], "label": s["name"]} for s in sensors]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("sensors"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                    )
                )
            }),
        )

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            if user_input.get("confirm"):
                for name in self._to_remove:
                    await self._do_remove(name)
            return self.async_create_entry(title="", data={})

        names = "\n".join(f"• {n}" for n in self._to_remove)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): bool,
            }),
            description_placeholders={"names": names},
        )

    async def _do_remove(self, name):
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        stored = await store.async_load() or {"sensors": []}

        match = next((s for s in stored["sensors"] if s["name"] == name), None)
        if not match:
            return

        sensor_id = match["id"]

        from homeassistant.helpers import entity_registry as er
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"filetrack_{sensor_id}")
        if entity_id:
            registry.async_remove(entity_id)

        stored["sensors"] = [s for s in stored["sensors"] if s["id"] != sensor_id]
        await store.async_save(stored)
