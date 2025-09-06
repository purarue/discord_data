## discord_data

Library to parse information from the discord data export, see more info [here](https://support.discord.com/hc/en-us/articles/360004027692).

The request to process the data has to be done manually, and it can take a while for them to deliver it to you.

This supports both the old CSV and new JSON formats for messages.

### Install:

Requires `python3.9+`. To install with pip, run:

    pip install discord_data

## Single Export

This takes the `messages` and `activity` directories as arguments, like:

```python
>>> from discord_data import parse_messages, parse_activity
>>> next(parse_messages("./discord/october_2020/messages"))
>>> next(parse_activity("./discord/october_2020/activity"))
```

`Message(mid='747951969171275807', dt=datetime.datetime(2020, 8, 25, 22, 54, 5, 726000, tzinfo=datetime.timezone.utc), channel=Channel(cid='464051583559139340', name='general', server_name='Dream World'), content='<:NotLikeThis:237729324885606403>', attachments='')`

`Activity(event_id='AQICfXBljgG+pYXCTRrwzy6MqgAAAAA=', event_type='start_listening', region_info=RegionInfo(city='cityNameHere', country_code='US', region_code='CA', time_zone='America/Los_Angeles'), fingerprint=Fingerprint(os='Mac OS X', os_version='16.1.0', browser='Discord Client', ip='216.58.195.78', isp=None, device=None, distro=None), timestamp=datetime.datetime(2016, 11, 26, 7, 8, 47))`

Each of these returns a `Generator`, so they only read from the (giant) JSON files as needed. If you want to process all the data, you can call `list` on it to consume the whole generator:

```python
from discord_data import parse_messages, parse_activity
msg = list(parse_messages("./discord/october_2020/messages"))
acts = list(parse_activity("./discord/october_2020/activity"))
```

The raw activity data includes lots of additional fields, this only includes items I thought would be useful. If you want to parse the JSON blobs yourself, you do so by using `from discord_data import parse_raw_activity`

If you just want to quickly load the parsed data into a REPL:

```shell
python3 -m discord_data ./discord/october_2020
```

That drops you into a python shell with access to `activity` and `messages` variables which include the parsed data

Or, to dump it to JSON:

```
python3 -m discord_data ./discord/october_2020 -o json > discord_data.json
```

## Merge Exports

Exports seem to be complete, but when a server or channel is deleted, all messages in that channel are deleted permanently, so I'd recommend periodically doing an export to make sure you don't lose anything.

I recommend you organize your exports like this:

```
discord
├── march_2021
│   ├── account
│   ├── activity
│   ├── messages
│   ├── programs
│   ├── README.txt
│   └── servers
└── october_2020
    ├── account
    ├── activity
    ├── messages
    ├── programs
    ├── README.txt
    └── servers
```

The `discord` folder at the top would be the `export_dir` keyword argument to the `merge_activity` and `merge_messages` functions, which call the underlying parse functions:

You can choose to supply the arguments with `export_dir` or `paths`:

```python
# locates the corresponding `messages` directories in the folder structure
list(merge_messages(export_dir="./discord"))`
# supply a list of the message directories yourself
list(merge_messages(paths=["./discord/march_2021/messages", "./discord/october_2020/messages"]))
```

If the format for the discord export changes, the parse/merge functions will still work, they just might yield errors as part of their output. To ignore those, you can do:

```python
for msg in merge_messages(export_dir="./discord"):
    if isinstance(msg, Exception):
        logger.warning(msg)
        continue
    # do something with msg
    print(msg.content)
```

Created to be used as part of [`HPI`](https://github.com/purarue/HPI)
