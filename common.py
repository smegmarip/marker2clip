import os
import re
import subprocess
import sys
import json
from urllib.parse import urlparse
import uuid
import requests
import warnings

import numpy as np
from typing import Any, List, Tuple
from glob import glob

try:
    import stashapi.log as log
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print(
        "You need to install the stashapp-tools (stashapi) python module. (CLI: pip install stashapp-tools)",
        file=sys.stderr,
    )

plugincodename = "stash2clip"
pluginhumanname = "Stash2Clip"

# Configuration/settings file... because not everything can be easily built/controlled via the UI plugin settings
# If you don't need this level of configuration, just define the default_settings here directly in code,
#    and you can remove the _defaults.py file and the below code
if not os.path.exists("config.py"):
    with open(plugincodename + "_defaults.py", "r") as default:
        config_lines = default.readlines()
    with open("config.py", "w") as firstrun:
        firstrun.write("from " + plugincodename + "_defaults import *\n")
        for line in config_lines:
            if not line.startswith("##"):
                firstrun.write(f"#{line}")

import config

default_settings = config.default_settings

PLUGIN_NAME = f"[{pluginhumanname}] "
STASH_URL = default_settings["stash_url"]
STASH_TMP = default_settings["stash_tmpdir"]
STASH_LOGFILE = default_settings["stash_logfile"]
BATCH_QTY = default_settings["batch_quantity"]
OUTPUT_DIR = default_settings["output_dir"]
DEFAULT_DURATION = default_settings["default_duration"]
CONVERTED_TAG_ID = default_settings["converted_tag_id"]

warnings.filterwarnings("ignore")


def stash_log(*args, **kwargs):
    """
    The stash_log function is used to log messages from the script.

    :param *args: Pass in a list of arguments
    :param **kwargs: Pass in a dictionary of key-value pairs
    :return: The message
    :doc-author: Trelent
    """
    messages = []
    for input in args:
        if not isinstance(input, str):
            try:
                messages.append(json.dumps(input, default=default_json))
            except:
                continue
        else:
            messages.append(input)
    if len(messages) == 0:
        return

    lvl = kwargs["lvl"] if "lvl" in kwargs else "info"
    message = " ".join(messages)

    if lvl == "trace":
        log.LEVEL = log.StashLogLevel.TRACE
        log.trace(message)
    elif lvl == "debug":
        log.LEVEL = log.StashLogLevel.DEBUG
        log.debug(message)
    elif lvl == "info":
        log.LEVEL = log.StashLogLevel.INFO
        log.info(message)
    elif lvl == "warn":
        log.LEVEL = log.StashLogLevel.WARNING
        log.warning(message)
    elif lvl == "error":
        log.LEVEL = log.StashLogLevel.ERROR
        log.error(message)
    elif lvl == "result":
        log.result(message)
    elif lvl == "progress":
        try:
            progress = min(max(0, float(args[0])), 1)
            log.progress(str(progress))
        except:
            pass
    log.LEVEL = log.StashLogLevel.INFO


def default_json(t):
    """
    The default_json function is used to convert a Python object into a JSON string.
    The default_json function will be called on every object that is returned from the StashInterface class.
    This allows you to customize how objects are converted into JSON strings, and thus control what gets sent back to the client.

    :param t: Pass in the time
    :return: The string representation of the object t
    :doc-author: Trelent
    """
    return f"{t}"


def get_config_value(section, prop):
    """
    The get_config_value function is used to retrieve a value from the config.ini file.

    :param section: Specify the section of the config file to read from
    :param prop: Specify the property to get from the config file
    :return: The value of a property in the config file
    :doc-author: Trelent
    """
    global _config
    return _config.get(section=section, option=prop)


def exit_plugin(msg=None, err=None):
    """
    The exit_plugin function is used to exit the plugin and return a message to Stash.
    It takes two arguments: msg and err. If both are None, it will simply print &quot;plugin ended&quot; as the output message.
    If only one of them is None, it will print that argument as either an error or output message (depending on which one was not None).
    If both are not none, then it will print both messages in their respective fields.

    :param msg: Display a message to the user
    :param err: Print an error message
    :return: A json object with the following format:
    :doc-author: Trelent
    """
    if msg is None and err is None:
        msg = pluginhumanname + " plugin ended"
    output_json = {}
    if msg is not None:
        stash_log(f"{msg}", lvl="debug")
        output_json["output"] = msg
    if err is not None:
        stash_log(f"{err}", lvl="error")
        output_json["error"] = err
    print(json.dumps(output_json))
    sys.exit()


def save_to_local(url, ext="jpg"):
    """
    The save_to_local function downloads a file from the internet and saves it to the local filesystem.

    :param url: Pass in the url of the file to download
    :param ext: Specify the file extension of the downloaded file
    :return: The filename of the downloaded file
    :doc-author: Trelent
    """
    directory = STASH_TMP if STASH_TMP.endswith(os.path.sep) else (STASH_TMP + os.path.sep)
    # Generate a unique filename
    filename = f"{directory}downloaded_{uuid.uuid4()}.{ext}"

    try:
        # Send an HTTP GET request to the URL
        response = requests.get(url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Open the local file in binary write mode and write the content from the URL to it
            with open(filename, "wb") as local_file:
                local_file.write(response.content)
            stash_log(f"Downloaded and saved file to {filename}", lvl="debug")
        else:
            stash_log(f"Failed to download file: {response.status_code}", lvl="error")
            return None
    except requests.exceptions.RequestException as e:
        stash_log(f"Failed to download file: {e}", lvl="error")
        return None

    return filename


def clear_tempdir():
    """
    The clear_tempdir function is used to clear the temporary directory of all files.
    This function is called when a user requests that the temp directory be cleared, or when an error occurs in which case it will attempt to clear the temp dir before exiting.

    :return: A boolean value
    :doc-author: Trelent
    """
    tmpdir = STASH_TMP if STASH_TMP.endswith(os.path.sep) else (STASH_TMP + os.path.sep)
    for f in glob(f"{tmpdir}*.jpg"):
        try:
            os.remove(f)
        except OSError as e:
            stash_log(f"could not remove {f}", lvl="error")
            continue
    stash_log("cleared temp directory.", lvl="debug")


def clear_logfile():
    """
    The clear_logfile function clears the logfile.

    :return: Nothing
    :doc-author: Trelent
    """
    if STASH_LOGFILE and os.path.exists(STASH_LOGFILE):
        with open(STASH_LOGFILE, "w") as file:
            pass


def to_integer(iter=[]):
    """
    The to_integer function takes a list of strings and converts them to integers.

    :param iter: Pass in a list of strings
    :return: A list of integers
    :doc-author: Trelent
    """
    return list(map(lambda x: int(x), iter))


def to_string(iter=[]):
    """
    The to_string function takes an iterable and returns a list of strings.

    :param iter: Specify the iterable object to be converted
    :return: A list of strings
    :doc-author: Trelent
    """
    return list(map(lambda x: str(x), iter))


def the_id(iter=[]):
    """
    The the_id function is used to extract the id field from a dictionary.
    It can be called in two ways:
        1) with a single argument, which should be either a dictionary or an iterable of dictionaries.  In this case, it will return the value of the &quot;id&quot; key for each element in that iterable (or just that one element if it's not an iterable).  If there is no &quot;id&quot; key present, then it will return None instead.
        2) with multiple arguments; each argument should be either a dictionary or an iterable of dictionaries.  In this case, it

    :param iter: Specify the iterable object to be mapped
    :return: A list of the ids from a list of dictionaries
    :doc-author: Trelent
    """
    return list(map(lambda x: x["id"] if isinstance(x, dict) and "id" in x else x, iter))


def omit_dict(obj: dict, keys: any):
    """
    The omit_dict function takes a dictionary and a list of keys to omit from the dictionary.
    It returns the original dict with all of those keys omitted.
    If you want to omit nested dictionaries, pass in another dict as an element in your list of keys, like so:

    :param obj: dict: Specify the dictionary that is to be filtered
    :param keys: any: Specify the keys that you want to omit from the object
    :return: A new object that omits the specified keys
    :doc-author: Trelent
    """
    _obj = obj.copy()
    try:
        if isinstance(_obj, dict):
            if isinstance(keys, str):
                return {k: v for k, v in _obj.items() if k != keys}
            elif isinstance(keys, list) or isinstance(keys, tuple):
                for key in keys:
                    if isinstance(key, dict) and len(key) == 1:
                        _key = list(key.keys())[0]
                        if _key in _obj:
                            if isinstance(key[_key], dict):
                                _obj[_key] = omit_dict(_obj[_key], key[_key])
                            elif isinstance(key[_key], str):
                                _obj = {k: v for k, v in _obj.items() if k != key[_key]}
                    elif isinstance(key, str):
                        _obj = {k: v for k, v in _obj.items() if k != key}
            elif isinstance(keys, dict) and len(keys) == 1:
                _key = list(keys.keys())[0]
                if _key in _obj:
                    if isinstance(keys[_key], dict):
                        _obj[_key] = omit_dict(_obj[_key], keys[_key])
                    elif isinstance(keys[_key], str) and isinstance(_obj[_key], dict):
                        _obj[_key] = {k: v for k, v in _obj[_key].items() if k != keys[_key]}
    except:
        return obj

    return _obj


def prepare_stash_list(iter=[]):
    """
    The prepare_stash_list function takes a list of strings and returns a unique list of strings.

    :param iter: Pass in a list of items to be converted to strings
    :return: A list of strings
    :doc-author: Trelent
    """
    return list(set(to_string(iter)))


def create_tag(stash: StashInterface, tagName):
    """
    The create_tag function creates a tag with the given name.

    :param stash: StashInterface: Pass in the stash object
    :param tagName: Create a tag with the name of the parameter
    :return: A tag object
    :doc-author: Trelent
    """
    return stash.create_tag({"name": tagName})


def find_tag(stash: StashInterface, tagName, create=False):
    """
    The find_tag function is used to find a tag in the stash.
    If the tag does not exist, it will be created if create=True.


    :param stash: StashInterface: Specify the type of object that is passed to the function
    :param tagName: Specify the name of the tag to find
    :param create: Create a tag if it doesn't exist
    :return: A tag object
    :doc-author: Trelent
    """
    return stash.find_tag(tagName, create)


def get_stash_video(vid_data):
    """
    The get_stash_video function takes in a video data object and returns the raw video file.

    :param vid_data: Get the video data from the stash
    :return: A dictionary with the following keys:
    :doc-author: Trelent
    """
    props = ["id", "path", "format", "width", "height", "duration", "frame_rate"]
    raw = None
    files = vid_data["files"]

    for file in files:
        test: str = file["path"]
        if os.path.exists(test):
            raw = {k: file[k] for k in props}
            break

    if raw is None:
        url = vid_data["paths"]["stream"]
        ext = "mp4"
        ext_match = re.search(r"\.([^.]+)$", files[0]["path"])
        if ext_match:
            ext = ext_match.group(1)
        raw = {k: file[k] for k in props}
        raw["path"] = save_to_local(url, ext)

    if raw is not None:
        raw["sprite"] = vid_data["paths"]["sprite"]
        raw["vtt"] = vid_data["paths"]["vtt"]
        valid = (
            ".m4v",
            ".mp4",
            ".mov",
            ".wmv",
            ".avi",
            ".mpg",
            ".mpeg",
            ".rmvb",
            ".rm",
            ".flv",
            ".asf",
            ".mkv",
            ".webm",
            ".flv",
            ".3gp",
        )
        if raw["path"].lower().endswith(valid):
            return raw

    return None


def frame_to_timecode(frame, fps):
    """
    The frame_to_timecode function converts a frame number to a timecode.

    :param frame: Specify the frame number, and fps is used to
    :param fps: Convert the frame number to seconds
    :return: A string in the format
    :doc-author: Trelent
    """
    seconds = frame / fps
    return seconds_to_timecode(seconds)


def seconds_to_timecode(seconds):
    """
    The seconds_to_timecode function takes a number of seconds and converts it to a timecode string.

    :param seconds: Convert the seconds to hours, minutes and seconds
    :return: A string that represents the timecode
    :doc-author: Trelent
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:06.3f}"


def extract_clip(input_path: str, marker: dict, duration: int, output_dir: str) -> str:
    """
    The extract_clip function takes an input video file, a marker dict, and a duration in seconds.
    It then creates the output directory if it doesn't exist already. It calculates the start time of
    the clip by adding the marker's &quot;seconds&quot; value to its own start_time variable. Then it uses ffmpeg
    to extract that clip from the input video and save it as an mp4 file in the output directory.

    :param input_path: str: Specify the path to the video file
    :param marker: dict: Pass in the marker information
    :param duration: int: Specify the length of the clip in seconds
    :param output_dir: str: Specify the directory where the output file will be saved
    :return: The path to the extracted clip
    :doc-author: Trelent
    """
    os.makedirs(output_dir, exist_ok=True)
    marker_start = marker["seconds"]
    start_time = seconds_to_timecode(marker_start)
    end_time = seconds_to_timecode(marker_start + duration)
    output_file = "_".join(["Clip", marker["id"], "Scene", marker["scene"]["id"], start_time, f"{duration}s"]) + ".mp4"
    output_path = os.path.join(output_dir, output_file)
    if os.path.isfile(output_path):
        stash_log(f"{output_file} already exists, skipping...")
    else:
        cmd = ["ffmpeg", "-y", "-ss", start_time, "-to", end_time, "-i", input_path, "-c", "copy", output_path]
        result = subprocess.run(cmd)
        return output_path if result.returncode == 0 else None
    return None
