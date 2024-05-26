import traceback
import time
from urllib.parse import unquote
from stashapi.stashapp import StashInterface
from common import DEFAULT_DURATION, OUTPUT_DIR, extract_clip, stash_log, get_stash_video


def convert_all_markers(stash: StashInterface, batch: int = 10):
    """
    The convert_all_markers function is a function that takes in the stash object and an optional batch size.
    It then finds all of the scene markers in the stash, and iterates through them one by one.
    For each marker it finds, it calls convert_marker on that marker.

    :param stash: StashInterface: Pass the stash object to the function
    :param batch: int: Limit the number of markers that are converted at once
    :return: A list of all the markers in the stash
    :doc-author: Trelent
    """
    total = 1
    counter = 0
    timeout = 5
    results = []
    while True:
        counter += 1
        _current, scenes = stash.find_scenes(f={"has_markers": "true"}, filter={"per_page": batch, "page": counter}, get_count=True)

        if counter == 1:
            total = int(_current)
            stash_log(f"found {total} scenes", lvl="info")

        _current = batch * (counter - 1)
        
        if _current >= total:
            break
    
        num_scenes = len(scenes)
        # stash_log("scenes", scenes, lvl="trace")
        stash_log(f"processing {num_scenes} / {_current} scenes", lvl="info")

        for i in range(num_scenes):
            scene = scenes[i]
            _current -= 1
            progress = (float(total) - float(_current)) / float(total)
            stash_log(progress, lvl="progress")
            stash_log(
                f"{round(progress * 100, 2)}%: ",
                f"evaluating scene index: {((counter - 1) * batch) + i} (id: {scene['id']})",
                lvl="info",
            )

            result = convert_single_scene(stash, scene["id"], DEFAULT_DURATION)
            results.append(result)

        stash_log("--end of loop--", lvl="debug")
        time.sleep(timeout)


def convert_single_scene(stash: StashInterface, scene_id: int, duration: int):
    """
    The convert_single_marker function takes a stash object, scene_id and duration as arguments.
    It then calls the get_scene_markers function on the stash object to retrieve all markers for that scene.
    If there are no markers it returns 0, otherwise it loops through each marker in the list of markers returned by get_scene_markers.
    For each marker it calls convert marker with that specific marker and duration as arguments.

    :param stash: StashInterface: Pass the stash object to the function
    :param scene_id: int: Identify the scene to be converted
    :param duration: int: Determine the length of the clip
    :return: A list of results
    :doc-author: Trelent
    """
    total = 1
    counter = 0
    timeout = 5
    results = []
    markers = stash.get_scene_markers(scene_id)
    total = len(markers) if markers else 0
    stash_log("markers", markers, lvl="trace")
    stash_log(f"found {total} markers", lvl="info")
    if total > 0:
        scene = get_scene(stash, scene_id)
        for i in range(total):
            counter += 1
            marker = markers[i]
            progress = float(counter) / float(total)
            stash_log(progress, lvl="progress")
            stash_log(
                f"{round(progress * 100, 2)}%: ",
                f"evaluating marker index: {counter} (id: {marker['id']})",
                lvl="info",
            )
            result = convert_marker(stash, marker, scene, duration)
            results.append(result)
    return result


def convert_marker(stash: StashInterface, marker: dict, scene: dict, duration: int):
    """
    The convert_marker function takes a marker and converts it into a clip.

    :param stash: StashInterface: Access the stash
    :param marker: dict: Get the marker data from the database
    :param duration: int: Specify the length of the clip to be extracted
    :return: A path to a video file
    :doc-author: Trelent
    """
    try:
        scene_path = None
        stash_log("Converting marker: ", marker, lvl="trace")
        if marker:
            if scene:
                scene_data = get_stash_video(scene)
                if scene_data is None:
                    stash_log("invalid video extension.", lvl="info")
                    return

                scene_path = scene_data["path"]
                return extract_clip(scene_path, marker, duration, OUTPUT_DIR)
    except Exception as ex:
        stash_log(f"{scene_path}: {ex}", lvl="error")
        stash_log(traceback.format_exc(), lvl="error")
    return None


def get_scene(stash: StashInterface, scene_id: int) -> dict:
    """
    The get_scene function takes a stash object and a scene_id as input.
    It then uses the find_scene function from the StashInterface class to return
    a dictionary containing all of the information about that scene.

    :param stash: StashInterface: Tell the function that stash is an object of type stashinterface
    :param scene_id: int: Specify the scene id to find
    :return: A dictionary with the following keys:
    :doc-author: Trelent
    """
    return stash.find_scene(scene_id)
