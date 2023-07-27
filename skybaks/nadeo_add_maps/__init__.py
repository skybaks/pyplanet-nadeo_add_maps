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
        self.api = NadeoServicesApi(settings.DEDICATED_USERNAME, settings.DEDICATED_PASSWORD)

    async def on_init(self) -> None:
        await self.api.create_session()

    async def on_start(self) -> None:
        await self.instance.command_manager.register(
            Command(command="add", aliases=[], target=self.add_nadeoservices_maps, namespace="nadeo",
                    description="Add maps from Nadeo servers using map UIDs")
                .add_param(name="map_uids", nargs="*", type=str, required=True)
        )

    async def add_nadeoservices_maps(self, player: Player, data, **kwargs) -> None:
        try:
            infos = await self.api.get_map_infos(data.map_uids)
        except Exception as e:
            logger.exception(e)
            infos = list()

        try:
            if not await self.instance.storage.driver.exists(os.path.join("UserData", "Maps", "PyPlanet-NadeoServices")):
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
                await self.instance.chat("$ff0Error: Can't add map $<$fff%s$>, Error: %s" % (map_info["name"], str(e)))
        
        try:
            await self.instance.map_manager.update_list(full_update=True)
        except:
            pass

        if juke_maps and len(added_map_uids) > 0:
            for juke_uid in added_map_uids:
                map_instance = await self.instance.map_manager.get_map(uid=juke_uid)
                if map_instance:
                    self.instance.apps.apps["jukebox"].insert_map(player, map_instance)
