import json

from datetime import datetime
from typing import NamedTuple, Any, cast

URL_BASE = "https://discord.com"

Json = dict[str, Any]


class Server(NamedTuple):
    server_id: int
    name: str


class Channel(NamedTuple):
    channel_id: int
    name: str | None
    server: Server | None  # if this is a guild (server), the server id/name

    @property
    def description(self) -> str:
        """
        small text description of where this message was found
        """
        if self.server is None:
            return self.name or f"channel ({self.channel_id})"
        else:
            if self.name is None:
                return f"{self.server.name} - {self.name}"
            else:
                return self.server.name


class Message(NamedTuple):
    message_id: int
    timestamp: datetime
    channel: Channel
    content: str
    attachments: str

    @property
    def link(self) -> str:
        """
        create a link to this message
        """
        cid = self.channel.channel_id
        server = self.channel.server
        # probably a PM?
        if server is None:
            return f"{URL_BASE}/channels/@me/{cid}/{self.message_id}"
        else:
            # in a server
            return f"{URL_BASE}/channels/{server.server_id}/{cid}/{self.message_id}"


class RegionInfo(NamedTuple):
    city: str
    country_code: str
    region_code: str
    time_zone: str


def _strip_quotes(o: str | None) -> str | None:
    if o:
        return o.strip('"')
    return o


class Fingerprint(NamedTuple):
    os: str | None
    os_version: str | None
    browser: str | None
    browser_user_agent: str | None
    ip: str | None
    isp: str | None
    device: str | None
    distro: str | None

    @classmethod
    def make(cls, blob: Json) -> "Fingerprint":
        return cls(**{f: _strip_quotes(blob.get(f)) for f in cls._fields})


class Activity(NamedTuple):
    event_id: str
    event_type: str
    region_info: RegionInfo | None
    # additional data that doesn't conform to this spec
    fingerprint: Fingerprint
    timestamp: datetime
    json_data_str: str | None

    @property
    def json_data(self) -> dict[str, str]:
        if self.json_data_str is None:
            return {}
        else:
            return cast(dict[str, str], json.loads(self.json_data_str))


def _default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


def serialize(obj: Any) -> str:
    import simplejson

    return simplejson.dumps(obj, default=_default, namedtuple_as_object=True)
