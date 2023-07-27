import logging
import os

from pyplanet.conf import settings
from pyplanet.apps.config import AppConfig
from pyplanet.contrib.command import Command
from pyplanet.apps.core.maniaplanet.models import Player

from .nadeo_services import NadeoServicesApi

logger = logging.getLogger(__name__)


class NadeoAddMaps(AppConfig):
    game_dependencies = ['trackmania_next']
    app_dependencies = ['core.maniaplanet', 'core.trackmania', 'core.shootmania']

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.api: NadeoServicesApi = None

    async def on_init(self) -> None:
        await self.initialize_api()

    async def on_start(self) -> None:
        await self.instance.command_manager.register(
            Command(command="add", aliases=[], target=self.add_nadeoservices_maps, namespace="nadeo",
                    perms="mx:add_remote", admin=True, description="Add maps from Nadeo servers using map UIDs")
                .add_param(name="map_uids", nargs="*", type=str, required=True)
        )

    async def initialize_api(self) -> None:
        logger.info("Looking for dedicated server credentials...")
        username: str = ""
        password: str = ""
        try:
            if await self.instance.storage.driver.is_file(os.path.join("UserData", "Config", "dedicated_cfg.txt")):
                logger.info("Found dedicated_cfg.txt in standard location, parsing for credentials")
                async with self.instance.storage.open(os.path.join("UserData", "Config", "dedicated_cfg.txt"), "r", encoding="utf-8") as dedicated_file:
                    text: str = await dedicated_file.read()
                    # Nadeo XML parser allows invalid characters to exist so we
                    # need to do this a hacky way
                    try:
                        comment_start_index = text.index("<!--")
                        while comment_start_index >= 0:
                            comment_end_index = text.index("-->")
                            text = text[0:comment_start_index] + text[comment_end_index+3:]
                            comment_start_index = text.index("<!--")
                    except:
                        pass
                    start_index = text.index("<masterserver_account>")
                    end_index = text.index("</masterserver_account>")
                    text = text[start_index+22:end_index]
                    login_start = text.index("<login>")
                    login_end = text.index("</login>")
                    password_start = text.index("<password>")
                    password_end = text.index("</password>")
                    username = text[login_start+7:login_end].strip()
                    password = text[password_start+10:password_end].strip()
                    pass
        except Exception as e:
            logger.info("Error getting credentials from dedicated_cfg.txt: %s" % (str(e),))

        if not username and not password:
            logger.info("Looking for credentials from PyPlanet settings...")
            try:
                username = settings.DEDICATED_USERNAME
                password = settings.DEDICATED_PASSWORD
            except Exception as e:
                logger.info("Error getting credentials from PyPlanet settings: %s" % (str(e)))

        if not username and not password:
            raise Exception("No dedicated credentials found, unable to continue! Specify your dedicated username and password in your PyPlanet setting with DEDICATED_USERNAME and DEDICATED_PASSWORD")

        logger.info("Got login information for dedicated server account with username '%s'" % (username,))
        self.api = NadeoServicesApi(username, password)
        await self.api.create_session()

    async def add_nadeoservices_maps(self, player: Player, data, **kwargs) -> None:
        try:
            infos = await self.api.get_map_infos(data.map_uids)
        except Exception as e:
            logger.exception(e)
            infos = list()

        if len(infos) == 0:
            await self.instance.chat("$ff0Error: API issue or map(s) not found, skipping download", player.login)

        try:
            if not await self.instance.storage.driver.exists(os.path.join("UserData", "Maps", "PyPlanet-NadeoServices")):
                logger.info("Creating folder UserData/Maps/PyPlanet-NadeoServices/")
                await self.instance.storage.driver.mkdir(os.path.join("UserData", "Maps", "PyPlanet-NadeoServices"))
        except Exception as e:
            logger.exception(e)

        juke_after_adding = await self.instance.setting_manager.get_setting("admin", "juke_after_adding", prefetch_values=True)
        juke_maps = await juke_after_adding.get_value()
        if "jukebox" not in self.instance.apps.apps:
            juke_maps = False
        added_map_uids = list()

        for map_info in infos:
            try:
                if self.instance.map_manager.playlist_has_map(map_info["mapUid"]):
                    raise Exception("Map is already in playlist, skipping download")

                response = await self.api.download(map_info["fileUrl"])
                map_filename = os.path.join("PyPlanet-NadeoServices", "%s.Map.Gbx" % (map_info["mapUid"],))
                async with self.instance.storage.open_map(map_filename, "wb+") as map_file:
                    await map_file.write(await response.read())
                    await map_file.close()

                result = await self.instance.map_manager.add_map(map_filename, save_matchsettings=False)

                if result:
                    added_map_uids.append(map_info["mapUid"])

                    message = "$ff0Admin $<$fff%s$> has added%s the map $<$fff%s$> from %s..." % (
                        player.nickname, " and juked" if juke_maps else "", map_info["name"], "NadeoServices"
                    )
                    await self.instance.chat(message)
                else:
                    raise Exception("Unknown error while adding the map")
            except Exception as e:
                logger.error(e)
                await self.instance.chat("$ff0Error: Can't add map $<$fff%s$>, Error: %s" % (map_info["name"], str(e)), player.login)
        
        try:
            await self.instance.map_manager.update_list(full_update=True)
        except:
            pass

        if juke_maps and len(added_map_uids) > 0:
            for juke_uid in added_map_uids:
                map_instance = await self.instance.map_manager.get_map(uid=juke_uid)
                if map_instance:
                    self.instance.apps.apps["jukebox"].insert_map(player, map_instance)
