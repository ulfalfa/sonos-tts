"""Support for command line notification services."""
import logging
import subprocess

import voluptuous as vol


from homeassistant.components.notify import ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_COMMAND, CONF_NAME, CONF_ENTITIES, CONF_ENTITY_ID, STATE_PAUSED, STATE_PLAYING
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_state_change

_LOGGER = logging.getLogger(__name__)
DOMAIN_SONOS = "sonos"
DOMAIN_MEDIA_PLAYER = "media_player"
DOMAIN_TTS = "tts"

COMMAND_JOIN = "join"
COMMAND_UNJOIN = "unjoin"
COMMAND_RESTORE = "restore"

ATTR_MASTER = "master"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_ENTITY_ID): cv.entity_id,
     vol.Optional(CONF_ENTITIES): cv.entity_ids}
)

ATTR_VOLUME = "volume_level"


def get_service(hass, config, discovery_info=None):
    """Get the Command Line notification service."""
    entities = config[CONF_ENTITIES]

    return SonosTTSNotificationService(hass, config[CONF_NAME], entities)


class SonosTTSNotificationService(BaseNotificationService):
    """Implement the notification service for the Command Line service."""

    def state_changed(self, entity_id, old_state, new_state):

        _LOGGER.debug("Track %s:  Player %s (Speaking=%s) from %s to %s",
                      self.name, entity_id, self.speaking, old_state.state, new_state.state)
        if self.speaking and entity_id == self.master:
            _LOGGER.debug("Restoring sonos")
            self.hass.services.call(
                DOMAIN_SONOS, COMMAND_RESTORE, {CONF_ENTITY_ID: self.entities}, True)
            self.speaking = False

    def state_logger(self, entity_id, old_state, new_state):
        _LOGGER.debug("Debug State %s (%s) from %s to %s",
                      entity_id, self.speaking, old_state, new_state)

    def __init__(self, hass, name, entities):
        """Initialize the service."""

        self.hass = hass
        self.name = name
        self.entities = entities

        tts_services = hass.services.services.get(DOMAIN_TTS)
        self.tts_plattform = list(tts_services.keys())[0]

        _LOGGER.debug("Setting up %s for tts %s with entities %s",
                      self.name, self.tts_plattform, self.entities)

        self.speaking = False
        track_state_change(
            self.hass, self.entities[0], self.state_changed, STATE_PLAYING, STATE_PAUSED)
        # track_state_change(self.hass, self.entities, self.state_logger)

    def send_message(self, message="", **kwargs):

        data = kwargs.get(ATTR_DATA)

        _LOGGER.debug("Making snapshot of %s", self.entities)
        self.hass.services.call(
            DOMAIN_SONOS, "snapshot", {CONF_ENTITY_ID: self.entities}, True
        )

        # unjoin all players
        self.hass.services.call(DOMAIN_SONOS, "unjoin", {
                                CONF_ENTITY_ID: self.entities}, True)

        # pause the current playback
        self.hass.services.call(DOMAIN_MEDIA_PLAYER, "media_pause", {
                                CONF_ENTITY_ID: self.entities}, True)

        # if we have more the one player, join them with master is the first player
        if len(self.entities) > 1:
            _LOGGER.debug("Join group %s", self.entities)
            self.hass.services.call(
                DOMAIN_SONOS, "join", {ATTR_MASTER: self.entities[0], CONF_ENTITY_ID: self.entities[1:]}, True)

        if data is not None and ATTR_VOLUME in data:
            volume = data.get(ATTR_VOLUME)
            _LOGGER.debug("Setting volume to %s", volume)
            self.hass.services.call(DOMAIN_MEDIA_PLAYER, "volume_set", {
                CONF_ENTITY_ID: self.entities, ATTR_VOLUME: volume}, True)

        self.speaking = True
        self.master = self.entities[0]
        _LOGGER.debug("Playing TTS %s on %s", message, self.master)
        self.hass.services.call(
            DOMAIN_TTS, self.tts_plattform, {CONF_ENTITY_ID: self.entities[0], "message": message}, True)
