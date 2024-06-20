import os
import subprocess
import psutil
import time
import requests
import json
import logging
from dotenv import load_dotenv
from pypresence import Presence
from auth import get_access_token

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s')

load_dotenv()

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
if not CLIENT_ID:
    raise ValueError("DISCORD_CLIENT_ID not set in environment variables")

DEFAULT_IMAGE_URL = "https://cdn.discordapp.com/avatars/1057191004219920464/ddfe4f21de1b98302459fcbfb7ba34a4.webp?size=256"

def get_tidal_pid():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'tidal' in proc.info['name'].lower():
            logging.debug(f"Found Tidal process: {proc.info}")
            return proc.info['pid']
    logging.warning("Tidal process not found.")
    return None

def get_window_title(pid):
    script = f"""
    tell application "System Events"
        set frontmostProcess to first process whose unix id is {pid}
        set windowName to name of front window of frontmostProcess
    end tell
    return windowName
    """
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    logging.debug(f"AppleScript result: {result.stdout.strip()}")
    return result.stdout.strip()

def get_tidal_string():
    tidal_pid = get_tidal_pid()
    if tidal_pid:
        title = get_window_title(tidal_pid)
        if title:
            logging.debug(f"Tidal window title: {title}")
            return title
    logging.warning("Unable to retrieve Tidal window title.")
    return None

def extract_song_info(tidal_string):
    if tidal_string:
        split_song_info = tidal_string.split(" - ")
        if len(split_song_info) == 2:
            logging.debug(f"Extracted song info: Title={split_song_info[0]}, Artist={split_song_info[1]}")
            return split_song_info
    logging.warning(f"Unable to extract song info from string: {tidal_string}")
    return "Unknown Title", "Unknown Artist"

def search_track(title, artist, access_token):
    url = "https://openapi.tidal.com/search"
    query = f"{title} {artist}"
    if len(query) > 100:
        query = query[:100]

    params = {
        "query": query,
        "type": "TRACKS",
        "offset": 0,
        "limit": 1,
        "countryCode": "US",
        "popularity": "WORLDWIDE"
    }
    headers = {
        "accept": "application/vnd.tidal.v1+json",
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/vnd.tidal.v1+json"
    }

    logging.debug(f"Searching track with URL: {url}, Params: {params}, Headers: {headers}")
    response = requests.get(url, headers=headers, params=params)

    if response.status_code not in (200, 207):
        logging.error(f"Error searching track: {response.status_code}")
        logging.error(f"Response content: {response.text}")
        return None

    data = response.json()
    logging.debug(f"Search response data: {json.dumps(data, indent=2)}")
    print(f"Search response data: {json.dumps(data, indent=2)}")

    if "tracks" in data and len(data["tracks"]) > 0:
        track_id = data["tracks"][0]["resource"]["id"]
        logging.debug(f"Found track ID: {track_id}")
        return track_id

    logging.warning("No tracks found in search response.")
    return None

def get_song_duration_and_image(track_id, access_token):
    url = f"https://openapi.tidal.com/tracks/{track_id}"
    params = {
        "countryCode": "US"
    }
    headers = {
        "accept": "application/vnd.tidal.v1+json",
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/vnd.tidal.v1+json"
    }

    logging.debug(f"Requesting song duration and image with URL: {url}, Params: {params}, Headers: {headers}")
    response = requests.get(url, params=params, headers=headers)

    if response.status_code != 200:
        logging.error(f"Error fetching song duration and image: {response.status_code}")
        logging.error(f"Response content: {response.text}")
        return 0, None

    data = response.json()
    logging.debug(f"Track details response data: {json.dumps(data, indent=2)}")
    print(f"Track details response data: {json.dumps(data, indent=2)}")
    duration = data.get("resource", {}).get("duration", 0)
    image_url = None

    if "album" in data["resource"] and "imageCover" in data["resource"]["album"]:
        image_cover = data["resource"]["album"]["imageCover"]
        print("Image cover var:", image_cover)
        if image_cover and len(image_cover) > 0:
            image_url = image_cover[0]["url"]

    logging.debug(f"Song duration: {duration}, Image URL: {image_url}")
    return duration, image_url

def update_discord_presence(client_id, title, artist, duration, image_url):
    RPC = Presence(client_id)
    RPC.connect()

    if duration is None:
        duration = 0

    if image_url is None:
        image_url = DEFAULT_IMAGE_URL

    start_time = int(time.time())
    end_time = start_time + duration

    logging.debug(f"Updating Discord presence: Title={title}, Artist={artist}, Duration={duration}, Image URL={image_url}")
    RPC.update(
        state=artist,
        details=title,
        start=start_time,
        end=end_time,
        large_image=image_url,
        large_text=title
    )

    while True:
        new_tidal_string = get_tidal_string()
        new_title, new_artist = extract_song_info(new_tidal_string)
        if new_title != title or new_artist != artist:
            title = new_title
            artist = new_artist
            track_id = search_track(new_title, new_artist, get_access_token())
            if track_id:
                duration, image_url = get_song_duration_and_image(track_id, get_access_token())
                if duration is None:
                    duration = 0
                if image_url is None:
                    image_url = DEFAULT_IMAGE_URL
                start_time = int(time.time())
                end_time = start_time + duration
                logging.debug(f"Updating Discord presence: Title={title}, Artist={artist}, Duration={duration}, Image URL={image_url}")
                RPC.update(
                    state=artist,
                    details=title,
                    start=start_time,
                    end=end_time,
                    large_image=image_url,
                    large_text=title
                )
        time.sleep(15)

def main():
    tidal_string = get_tidal_string()
    title, artist = extract_song_info(tidal_string)
    access_token = get_access_token()
    track_id = search_track(title=title, artist=artist, access_token=access_token)
    if track_id:
        duration, image_url = get_song_duration_and_image(track_id, access_token)
        update_discord_presence(CLIENT_ID, title=title, artist=artist, duration=duration, image_url=image_url)
    else:
        logging.error("Track not found.")

if __name__ == "__main__":
    main()
