import logging
from pathlib import Path
from typing import Set, Optional, Iterator, List, Sequence, Union

from .model import Json, Message, Activity
from .error import Res
from .common import PathIsh, expand_path
from .parse import (
    parse_messages,
    parse_raw_activity,
    _parse_activity_blob,
)

MESSAGES_DIRS = ["messages", "Messages"]
ACTIVITY_DIRS = ["activity", "Activity"]


# handles resolving the paths from the top-level export_dir
# or a list of paths
def _list_exports(
    # messages or activity, one or more paths to match
    search_for_folder: Union[str, List[str]],
    export_dir: Optional[PathIsh] = None,
    paths: Optional[Sequence[PathIsh]] = None,
    logger: Optional[logging.Logger] = None,
) -> List[Path]:
    sfolders = (
        [search_for_folder] if isinstance(search_for_folder, str) else search_for_folder
    )
    assert isinstance(sfolders, list) and len(sfolders) > 0

    exports: List[Path] = []
    for folder_name in sfolders:
        if paths is not None:
            for p in map(expand_path, paths):
                if not p.name == folder_name:
                    if logger:
                        logger.debug(f"Expected {p} to end with {folder_name}...")
                exports.append(p)
        else:
            if export_dir is None:
                raise RuntimeError(
                    "Did not supply an 'export_dir' (top-level dir with multiple exports) or 'paths' (the activity/messages dirs themselves"
                )
            for p in expand_path(export_dir).iterdir():
                # sanity-check, to make sure this is the right path
                fdir = p / folder_name
                if fdir.exists():
                    exports.append(fdir)
                else:
                    if logger:
                        logger.debug(
                            f"Directory not found: Expected {folder_name} directory at {fdir}"
                        )
    return exports


def merge_raw_activity(
    *,
    export_dir: Optional[PathIsh] = None,
    paths: Optional[Sequence[PathIsh]] = None,
    logger: Optional[logging.Logger] = None,
) -> Iterator[Json]:
    emitted: Set[str] = set()
    for p in _list_exports(ACTIVITY_DIRS, export_dir, paths, logger=logger):
        for blob in parse_raw_activity(p, logger=logger):
            key: str = blob["event_id"]
            if key in emitted:
                continue
            yield blob
            emitted.add(key)


def merge_activity(
    *,
    export_dir: Optional[PathIsh] = None,
    paths: Optional[Sequence[PathIsh]] = None,
    logger: Optional[logging.Logger] = None,
) -> Iterator[Res[Activity]]:
    for rawact in merge_raw_activity(export_dir=export_dir, paths=paths, logger=logger):
        try:
            yield _parse_activity_blob(rawact)
        except Exception as e:
            yield e


def merge_messages(
    *,
    export_dir: Optional[PathIsh] = None,
    paths: Optional[Sequence[PathIsh]] = None,
    logger: Optional[logging.Logger] = None,
) -> Iterator[Res[Message]]:
    emitted: Set[int] = set()
    for p in _list_exports(MESSAGES_DIRS, export_dir, paths, logger=logger):
        for msg in parse_messages(p):
            if isinstance(msg, Exception):
                yield msg
                continue
            key: int = msg.message_id
            if key in emitted:
                continue
            yield msg
            emitted.add(msg.message_id)
