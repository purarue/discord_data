import json
import csv
import logging

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional, Dict, List, Any, Union


from .model import Message, Channel, Json, Activity, RegionInfo, Fingerprint, Server
from .common import expand_path, PathIsh
from .error import Res


def _get_self_user_id(export_root_dir: PathIsh) -> str:
    base = expand_path(export_root_dir)
    user_info_f: list[Path] = [
        base / acc_name / "user.json" for acc_name in ["account", "Account"]
    ]
    found_l = [f for f in user_info_f if f.exists()]
    if not found_l:
        raise RuntimeError(f"Could not find user.json in any of {user_info_f}")
    found = found_l[0]
    user_json = json.loads(found.read_text())
    return str(user_json["id"])


# timezone aware
DT_FORMATS = [r"%Y-%m-%d %H:%M:%S.%f%z", r"%Y-%m-%d %H:%M:%S%z"]


def _parse_message_datetime(ds: str) -> datetime:
    for dfmt in DT_FORMATS:
        try:
            return datetime.strptime(ds, dfmt)
        except ValueError:
            pass
    # try as a fallback?
    return _parse_activity_datetime(ds)


def _parse_activity_datetime(ds: str) -> datetime:
    try:
        d = ds.strip('"').rstrip("Z")
        naive = datetime.fromisoformat(d)
        return naive.replace(tzinfo=timezone.utc)
    except ValueError as v:
        print(f"Could not parse datetime with any of the known formats: {ds}")
        raise v


def parse_messages(messages_dir: PathIsh) -> Iterator[Res[Message]]:
    pmsg_dir: Path = expand_path(messages_dir)
    # get user id

    # parse index
    index_f = pmsg_dir / "index.json"
    if not index_f.exists():
        yield RuntimeError(f"Message index 'index.json' doesn't exist at {index_f}")
        return
    index: Dict[str, Optional[str]] = json.loads(index_f.read_text())

    # get individual message directories
    msg_dirs: List[Path] = list(
        filter(lambda d: d.is_dir() and not d.name.startswith("."), pmsg_dir.iterdir())
    )
    for msg_chan in msg_dirs:
        # channel.json has some metadata about the channel/server
        channel_info_f: Path = msg_chan / "channel.json"
        if not channel_info_f.exists():
            yield RuntimeError(
                f"Channel info 'channel.json' doesn't exist at {channel_info_f}"
            )
            continue
        channel_json: Dict[str, Any] = json.loads(channel_info_f.read_text())

        # optionally, find server information
        server_info: Optional[Server] = None

        # if the channel.json included guild (server) info
        if (
            "guild" in channel_json
            and "id" in channel_json["guild"]
            and "name" in channel_json["guild"]
        ):
            server_info = Server(
                server_id=int(channel_json["guild"]["id"]),
                name=channel_json["guild"]["name"],
            )

        channel_name: Optional[str] = index.get(channel_json["id"])

        if "id" not in channel_json:
            yield RuntimeError(f"Channel id not found in {channel_info_f}")
            continue
        channel_obj: Channel = Channel(
            channel_id=int(channel_json["id"]),
            name=channel_name,
            server=server_info,
        )

        channel_csv = msg_chan / "messages.csv"
        if channel_csv.exists():
            # read CSV file to get messages
            with (msg_chan / "messages.csv").open(
                "r", encoding="utf-8", newline=""
            ) as f:
                csv_reader = csv.reader(
                    f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
                )
                next(csv_reader)  # ignore header row
                for row in csv_reader:
                    try:
                        yield Message(
                            message_id=int(row[0]),
                            timestamp=_parse_message_datetime(row[1]),
                            channel=channel_obj,
                            content=row[2],
                            attachments=row[3],
                        )
                    except Exception as e:
                        yield e
        else:
            json_file = msg_chan / "messages.json"
            if not json_file.exists():
                yield RuntimeError(f"No messages file found in in {msg_chan}")
                continue

            # read JSON file to get messages
            messages_json: List[Dict[str, Any]] = json.loads(json_file.read_text())

            for msg in messages_json:
                try:
                    yield Message(
                        message_id=int(msg["ID"]),
                        timestamp=_parse_message_datetime(msg["Timestamp"]),
                        channel=channel_obj,
                        content=msg["Contents"],
                        attachments=msg.get("Attachments", ""),
                    )
                except Exception as e:
                    yield e


def _parse_activity_blob(blob: Json) -> Activity:
    reginfo = None
    try:
        reginfo = RegionInfo(
            city=blob["city"],
            country_code=blob["country_code"],
            region_code=blob["region_code"],
            time_zone=blob["time_zone"],
        )
    except KeyError:
        pass
    json_data: Dict[str, Union[str, None]] = {}
    event_type = blob["event_type"]
    if event_type == "launch_game":
        json_data["game"] = blob.get("game")
    elif event_type == "add_reaction":
        json_data["message_id"] = blob.get("message_id")
        json_data["emoji_name"] = blob.get("emoji_name")
    elif event_type == "game_opened":
        json_data["game"] = blob.get("game")
    elif event_type == "application_opened":
        json_data["application"] = blob.get("application_name")
    json_clean: Dict[str, str] = {k: v for k, v in json_data.items() if v is not None}
    return Activity(
        event_id=blob["event_id"],
        event_type=event_type,
        region_info=reginfo,
        fingerprint=Fingerprint.make(blob),
        timestamp=_parse_activity_datetime(blob["timestamp"]),
        json_data_str=json.dumps(json_clean) if json_clean else None,
    )


def parse_activity(
    events_dir: PathIsh, logger: Optional[logging.Logger] = None
) -> Iterator[Res[Activity]]:
    """
    Return useful fields from the JSON blobs
    """
    for x in parse_raw_activity(events_dir, logger):
        if x.get("predicted_gender") is not None or x.get("predicted_age") is not None:
            # newer (2023ish) export have a few (2-3) of these events
            # they don't have any useful info apart from some probabilities of user's gender/age
            # don't have any event_id or event_type either so we can't really parse them
            continue
        try:
            yield _parse_activity_blob(x)
        except Exception as e:
            yield e


def parse_raw_activity(
    events_dir: PathIsh, logger: Optional[logging.Logger] = None
) -> Iterator[Json]:
    """
    Return all the objects from the activity directory, as
    JSON blobs
    """
    for activity_f in expand_path(events_dir).rglob("*.json"):
        if logger is not None:
            logger.debug(f"Parsing {activity_f}...")
        # not a 'json file', this has json objects, one per line
        for line in activity_f.open("r"):
            yield json.loads(line)
