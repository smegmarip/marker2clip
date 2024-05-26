import json
import os
import glob
import sys
import subprocess

os.chdir(os.path.dirname(os.path.realpath(__file__)))

from common import (
    stash_log,
    exit_plugin,
    plugincodename,
    pluginhumanname,
    default_settings,
    clear_tempdir,
    clear_logfile,
    STASH_TMP,
    BATCH_QTY,
    DEFAULT_DURATION,
)
from convert import convert_all_markers, convert_single_scene

try:
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print(
        "You need to install the stashapp-tools (stashapi) python module. (CLI: pip install stashapp-tools)",
        file=sys.stderr,
    )


def main():
    """
    The main function is the entry point for this plugin.

    :return: A string
    :doc-author: Trelent
    """
    global stash

    json_input = json.loads(sys.stdin.read())
    FRAGMENT_SERVER = json_input["server_connection"]
    stash = StashInterface(FRAGMENT_SERVER)

    ARGS = False
    PLUGIN_ARGS = False
    HOOKCONTEXT = False

    # Task Button handling
    try:
        PLUGIN_ARGS = json_input["args"]["mode"]
        ARGS = json_input["args"]
    except:
        pass

    # Check if the directory exists
    if not os.path.exists(STASH_TMP):
        os.makedirs(STASH_TMP)
        stash_log(f"directory: '{STASH_TMP}' created.", lvl="debug")

    # Clear temp directory
    clear_tempdir()

    # Clear log file
    clear_logfile()

    if PLUGIN_ARGS:
        stash_log("--Starting " + pluginhumanname + " Plugin --", lvl="debug")

        if "convertAll" in PLUGIN_ARGS:
            stash_log("running convertAll", lvl="info")
            convert_all_markers(stash=stash, batch=BATCH_QTY)

        if "convertMarker" in PLUGIN_ARGS:
            stash_log("running convertMarker", lvl="info")
            if "marker_id" in ARGS:
                scene_id = ARGS["scene_id"]
                if scene_id is not None:
                    duration = ARGS["duration"] if "duration" in ARGS else DEFAULT_DURATION
                    duration = int(duration) if duration not in [False, None, "None", "null"] else DEFAULT_DURATION
                    result = convert_single_scene(stash=stash, scene_id=scene_id, duration=duration)
                    if result is not None:
                        stash_log("convertMarker =", result, lvl="info")
                        exit_plugin(msg="ok")
            stash_log("convertMarker =", {"result": None}, lvl="info")

    exit_plugin(msg="ok")


if __name__ == "__main__":
    main()
