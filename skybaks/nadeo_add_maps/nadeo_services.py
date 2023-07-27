import logging
import aiohttp
import json
from base64 import b64decode
from datetime import datetime

logger = logging.getLogger(__name__)


class NadeoServicesApi:
    def __init__(self, dedicated_login: str, dedicated_password: str) -> None:
        self.username: str = dedicated_login
        self.password: str = dedicated_password
        self.json_web_token: dict = dict()
        self.token_expire: datetime = datetime(1970, 1, 1)
        self.token_refresh: datetime = datetime(1970, 1, 1)
        self.session: aiohttp.ClientSession = None

    @property
    def auth_valid(self) -> bool:
        if (self.json_web_token
            and datetime.now() < self.token_expire
            and datetime.now() < self.token_refresh):
            return True
        return False

    async def create_session(self) -> None:
        self.session = await aiohttp.ClientSession().__aenter__()

    async def end_session(self) -> None:
        if self.session and hasattr(self.session, "__aexit__"):
            await self.session.__aexit__()

    async def authenticate(self) -> None:
        AUTH_INIT_URL = "https://prod.trackmania.core.nadeo.online/v2/authentication/token/basic"
        AUTH_REFR_URL = "https://prod.trackmania.core.nadeo.online/v2/authentication/token/refresh"

        auth_req_data = json.dumps(dict(audience="NadeoServices"))
        headers = {"Content-Type": "application/json"}
        if (self.json_web_token
            and datetime.now() < self.token_expire
            and datetime.now() > self.token_refresh):
            logger.info("Refreshing NadeoServices authentication token")
            headers["Authorization"] = "nadeo_v1 t=%s" % (self.json_web_token["refreshToken"],)
            response = await self.session.post(AUTH_REFR_URL, data=auth_req_data, headers=headers)
        else:
            logger.info("Requesting NadeoServices authentication token")
            response = await self.session.post(
                AUTH_INIT_URL,
                data=auth_req_data,
                headers=headers,
                auth=aiohttp.BasicAuth(self.username, self.password)
            )
        if response.status != 200:
            logger.error("Error returned from NadeoServices authentication")
            self.json_web_token = dict()
            self.token_expire = datetime(1970, 1, 1)
            self.token_refresh = datetime(1970, 1, 1)
        else:
            self.json_web_token = json.loads(await response.content.read())
            self.token_expire, self.token_refresh = self.get_times(self.json_web_token)

    async def get_map_infos(self, map_uids: "str | list[str]") -> list:
        MAP_LOOKUP_URL = "https://prod.trackmania.core.nadeo.online/maps/?mapUidList="
        if not self.auth_valid:
            await self.authenticate()
        uids = list()
        if isinstance(map_uids, str):
            uids.append(map_uids)
        elif isinstance(map_uids, list):
            uids = map_uids
        else:
            logger.error("Unsupported type used in get_map_infos")
        headers = {
            "Authorization": "nadeo_v1 t=%s" % (self.json_web_token["accessToken"],),
            "Content-Type": "application/json"
        }
        response = await self.session.get(MAP_LOOKUP_URL + ",".join(map_uids), headers=headers)
        if response.status != 200:
            logger.error("Error when requesting map infos")
        else:
            return json.loads(await response.content.read())

    async def download(self, url: str) -> None:
        response = await self.session.get(url)
        if response.status != 200:
            logger.error("Error when downloading map from " + str(url))
        return response

    @staticmethod
    def get_times(json_web_token: dict) -> "tuple[datetime, datetime]":
        access_token = json_web_token.get("accessToken")
        split_token = access_token.split(".")
        if len(split_token) == 3:
            payload_str = b64decode(split_token[1] + "==").decode("utf-8")
            payload = json.loads(payload_str)
            expiration = datetime.fromtimestamp(payload.get("exp"))
            refresh = datetime.fromtimestamp(payload.get("rat"))
            return expiration, refresh
        return datetime(1970, 1, 1), datetime(1970, 1, 1)

