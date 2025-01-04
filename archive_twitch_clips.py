import argparse
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

import pytz
from luscioustwitch import *

from util.mediacms import MediaCMS_API

CLIP_ID_REGEX = re.compile(r'([A-Za-z0-9\-_]{12,})')
CLIP_LINK_REGEX = re.compile(r'https?:\/\/clips\.twitch\.tv\/([A-Za-z0-9\-_]{12,})')
MOBILE_LINK_REGEX = re.compile(r'https?:\/\/m\.twitch\.tv\/clip\/([A-Za-z0-9\-_]{12,})')

def get_clip_id_from_string(clip_string : str) -> str:
  m = CLIP_LINK_REGEX.match(clip_string)
  if m:
    return m.group(1)
  m = MOBILE_LINK_REGEX.match(clip_string)
  if m:
    return m.group(1)
  m = CLIP_ID_REGEX.match(clip_string)
  if m:
    return m.group(1)
  return None

def get_clip_true_time(twitch_api, clip_info):
  if clip_info['video_id'] != '':
    video_info = twitch_api.get_video(clip_info['video_id'])
    offset = int(clip_info['vod_offset'])
    vod_start = datetime.strptime(video_info['created_at'], TWITCH_API_TIME_FORMAT)
    clip_time = vod_start + timedelta(seconds=offset)
    return clip_time
  else:
    return datetime.strptime(clip_info['created_at'], TWITCH_API_TIME_FORMAT)

def download_and_archive_clip(twitch_api : TwitchAPI, gql_api : TwitchGQL_API, mediacms_api : MediaCMS_API, clip_id : str, delete_after : bool) -> bool:
  try:
    search_result = mediacms_api.search(clip_id.replace("-", " "))
  except Exception as e:
    print(f"Error searching for \"{clip_id}\" in MediaCMS library.")
    print(e)
  
  if int(search_result['count']) > 0:
    print(f"Found match for clip ID '{clip_id}' in archive here {search_result['results'][0]['url']}. Skipping.")
    return False
  
  search_result = mediacms_api.search(clip_id)
  
  if int(search_result['count']) > 0:
    print(f"Found match for clip ID '{clip_id}' in archive here {search_result['results'][0]['url']}. Skipping.")
    return False
  
  search_result = mediacms_api.search(f'https://clips.twitch.tv/{clip_id.replace("-", " ")}')
  
  if int(search_result['count']) > 0:
    print(f"Found match for clip ID '{clip_id}' in archive here {search_result['results'][0]['url']}. Skipping.")
    return False
  
  search_result = mediacms_api.search(f'https://clips.twitch.tv/{clip_id}')
  
  if int(search_result['count']) > 0:
    print(f"Found match for clip ID '{clip_id}' in archive here {search_result['results'][0]['url']}. Skipping.")
    return False
  
  clip_info = twitch_api.get_clip(clip_id)
  clip_filename = f"{clip_info['view_count']}_[[{clip_info['id']}]].mp4"
  
  clip_title = clip_info['title']
  
  upload_time = datetime.strptime(clip_info['created_at'], TWITCH_API_TIME_FORMAT).strftime("%Y-%m-%d %H:%M:%S")
  
  category_info = twitch_api.get_category_info(clip_info['game_id'], is_name = False)
  
  clip_description = f"""{clip_info['view_count']} views

{upload_time}

Category: {category_info['name']}

Clip link: https://clips.twitch.tv/{clip_info['id']}

Clipped by {clip_info['creator_name']}"""
  
  print(f'Downloading clip {clip_id}...')
  success = gql_api.download_clip(clip_id, clip_filename, True)
  
  if success:
    print(f'Uploading clip to MediaCMS with title "{clip_title}"')
    resp = mediacms_api.upload_clip(clip_filename, clip_title, clip_description)
    
  if delete_after:
    os.remove(clip_filename)
    
  return True

def download_video(twitch_api : TwitchAPI, gql_api : TwitchGQL_API, video_id : str, delete_after : bool) -> bool:
  video_info = twitch_api.get_video(video_id)
  base_filename = f"{video_info['created_at']}_[[{video_info['id']}]]".replace(":", "")
  txt_filename = f"{base_filename}.txt"
  video_filename = f"{base_filename}.ts"
  final_video_filename = f"{base_filename}.mp4"
  
  video_title = video_info['title']
  
  upload_time = datetime.strptime(video_info['created_at'], TWITCH_API_TIME_FORMAT).strftime("%Y-%m-%d %H:%M:%S")
  
  video_description = f"""Title: {video_title}
  
{upload_time}

{json.dumps(video_info, indent=2)}"""
  
  with open(txt_filename, 'w', encoding="UTF-8") as f:
    f.write(video_description)
    f.close()
  
  success = True
  if not os.path.exists(video_filename) and not os.path.exists(final_video_filename):
    print(f'Downloading video {video_id}...')
    success = gql_api.download_video(video_id, video_filename, "720", False)
  
    print(f"Converting temp file to mp4...")
    o = subprocess.run(['ffmpeg', "-y", "-i", video_filename, "-map", "0:v", "-map", "0:a", "-vcodec", "libx265", "-crf", "24", final_video_filename], capture_output = True)
    
    if delete_after:
      os.remove(video_filename)
    
  return success

def archive_from_file(twitch_api : TwitchAPI, gql_api : TwitchGQL_API, mediacms_api : MediaCMS_API, filepath : Path, output_folder : Path, delete_after : bool):
  print(f"Archiving clips from {filepath}")
  if not os.path.exists(filepath):
    print(f"{filepath} does not exist!")
    return
  
  with open(filepath, 'r') as clipsfile:
    clips = clipsfile.readlines()
    
  os.chdir(output_folder)
    
  for clip in clips:
    clip_id = get_clip_id_from_string(clip)
    if clip_id is None:
      print(f"Failed to locate clip ID in {clip}")
      continue
    
    download_and_archive_clip(twitch_api, gql_api, mediacms_api, clip_id, delete_after)
      
def archive_clip(twitch_api : TwitchAPI, gql_api : TwitchGQL_API, mediacms_api : MediaCMS_API, clip_string : str, output_folder : Path, delete_after : bool):
  print(f"Archiving clip {clip_string}")
  clip_id = get_clip_id_from_string(clip_string)
  if clip_id is None:
    print(f"Failed to locate clip ID in {clip_string}")
    return
  
  os.chdir(output_folder)
  
  download_and_archive_clip(twitch_api, gql_api, mediacms_api, clip_id, delete_after)
  
def archive_range(twitch_api : TwitchAPI, gql_api : TwitchGQL_API, mediacms_api : MediaCMS_API, start : str, end : str, minimum : int, broadcaster : str, timezone : str, category_name : str, output_folder : Path, delete_after : bool):
  print(f"Archiving {broadcaster} clips from {start} to {end} with at least {minimum} views.")
  
  os.chdir(output_folder)
  
  local = pytz.timezone(timezone)

  start_datetime = local.localize(datetime.strptime(args.start, TWITCH_API_TIME_FORMAT), is_dst=None)
  end_datetime = local.localize(datetime.strptime(args.end, TWITCH_API_TIME_FORMAT), is_dst=None)
  
  broadcaster_id = twitch_api.get_user_id(broadcaster)

  num_clips = 0
  clip_ids = []
  continue_fetching = True

  clip_params = {
    "first": 50,
    "broadcaster_id": broadcaster_id,
    "started_at": start_datetime.astimezone(pytz.utc).strftime(TWITCH_API_TIME_FORMAT),
    "ended_at": end_datetime.astimezone(pytz.utc).strftime(TWITCH_API_TIME_FORMAT)
  }
  
  category_id = None
  if category_name != "":
    category_id = twitch_api.get_category_id(category_name)
    print(f"{category_name} - {category_id}")
  
  while continue_fetching:
    clips, cursor = twitch_api.get_clips(params=clip_params)

    if cursor != "":
      clip_params["after"] = cursor
    else:
      continue_fetching = False

    for clip in clips:
      if clip['id'] in clip_ids:
        print(f"Got clip {clip['id']} twice while fetching")
        continue
      
      clip_match = True
      
      if (category_id is not None) and (category_id != clip['game_id']):
        clip_match = False
      
      if clip_match:
        newclip = download_and_archive_clip(twitch_api, gql_api, mediacms_api, clip['id'], delete_after)
        num_clips += 1 if newclip else 0
        clip_ids.append(clip['id'])

      views = int(clip["view_count"])
      if views < minimum:
        continue_fetching = False
        break
  print(f"{num_clips} new clips found & archived.")
  
def archive_vod_range(twitch_api : TwitchAPI, gql_api : TwitchGQL_API, mediacms_api : MediaCMS_API, period : str, vod_type : str, broadcaster : str, category_name : str, output_folder : Path, delete_after : bool):
  print(f"Archiving {broadcaster} vods within period {period}.")
  
  os.chdir(output_folder)
  
  broadcaster_id = twitch_api.get_user_id(broadcaster)

  video_params = {
    "user_id": broadcaster_id,
    "period": period,
    "sort": "time",
    "type": vod_type
  }
  
  category_id = None
  if category_name != "":
    category_id = twitch_api.get_category_id(category_name)
    print(f"{category_name} - {category_id}")
      
  all_videos = twitch_api.get_all_videos(video_params)
  
  is_live = twitch_api.is_user_live(broadcaster_id)
  
  num_videos = 0
  video_ids = []
  tnow = datetime.now()
  for video in all_videos:
    if is_live:
      time_since_published : timedelta = tnow - datetime.strptime(video['published_at'], TWITCH_API_TIME_FORMAT)
      if time_since_published.total_seconds() < (12 * 3600):
        print(f"Skipping video published at {video['published_at']}")
        continue
    
    if video["id"] in video_ids:
      print(f"Got video {video['id']} twice.")
      continue
    
    video_match = True
      
    if (category_id is not None) and (category_id != video['game_id']):
      video_match = False
      
    if video_match:
      success = download_video(twitch_api, gql_api, video['id'], delete_after)
      num_videos += 1 if success else 0
      video_ids.append(video['id'])
      
  print(f"{num_videos} videos downloaded.")

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--secrets", '-s', default = './secrets.json', help = "File containing Twitch and MediaCMS credentials.")
  parser.add_argument("--mediaurl", '-m', default = 'https://clips.itswill.org', help = "MediaCMS URL")
  parser.add_argument("--folder", '-o', default = './output/', help = "Folder to download clips into.")
  parser.add_argument('--delete', '-d', action = 'store_true', help = "Delete clips after archiving.")
  
  subparser = parser.add_subparsers(help = "sub-commands help")
  
  sp = subparser.add_parser("file", help = "Archive clips from a file containing IDs/links.")
  sp.set_defaults(cmd = 'file')
  sp.add_argument("--file", '-f', required = True, help = "Filepath containing clip IDs or links.")
  
  sp = subparser.add_parser("single", help = "Archive a single clip from its clip ID.")
  sp.set_defaults(cmd = 'single')
  sp.add_argument("--id", '-i', required = True, help = "Clip ID.")
  
  sp = subparser.add_parser("range", help = "Archive clips within a time range.")
  sp.set_defaults(cmd = 'range')
  sp.add_argument('--start', "-s", required=True, help="Start of clip search")
  sp.add_argument('--end', "-e", default=datetime.now().strftime(TWITCH_API_TIME_FORMAT), help="End of clip search")
  sp.add_argument('--minimum', "-m", default=25, type=int, help="Minimum number of views for a clip to get downloaded")
  sp.add_argument('--broadcaster', '-b', default="itswill", help="Broadcaster name.")
  sp.add_argument('--timezone', '-z', default="America/Los_Angeles", help="Timezone for start/end timestamps.")
  sp.add_argument('--category', '-c', default = "", help = "Only fetch clips in one game/category.")
  
  sp = subparser.add_parser("vodrange", help = "Archive clips within a time range.")
  sp.set_defaults(cmd = 'vodrange')
  sp.add_argument('--period', "-p", required=True, help="Period of vod search. DOES NOT WORK TWITCH API IS BROKEN!", choices = ["all", "day", "month", "week"])
  sp.add_argument('--type', "-t", required=True, help="Type of vods.", choices = ["all", "archive", "highlight", "upload"])
  sp.add_argument('--broadcaster', '-b', default="itswill", help="Broadcaster name.")
  sp.add_argument('--category', '-c', default = "", help = "Only fetch clips in one game/category.")
  
  args = parser.parse_args()
  
  with open(args.secrets, 'r') as cred_file:
    cred_json = json.load(cred_file)
    twitch_api = TwitchAPI(credentials = cred_json['TWITCH'])
    gql_api = TwitchGQL_API()
    mediacms_api = MediaCMS_API(args.mediaurl, (cred_json['MEDIACMS']['USERNAME'], cred_json['MEDIACMS']['PASSWORD']))
    
  output_folder = Path(args.folder)
  if not os.path.exists(output_folder):
    os.makedirs(output_folder)
  
  if args.cmd == 'file':
    filepath = Path(args.file)
    archive_from_file(twitch_api, gql_api, mediacms_api, filepath, output_folder, args.delete)
    
  if args.cmd == 'single':
    archive_clip(twitch_api, gql_api, mediacms_api, args.id, output_folder, args.delete)
    
  if args.cmd == 'range':
    archive_range(twitch_api, gql_api, mediacms_api, args.start, args.end, args.minimum, args.broadcaster, args.timezone, args.category, output_folder, args.delete)
    
  if args.cmd == 'vodrange':
    archive_vod_range(twitch_api, gql_api, mediacms_api, args.period, args.type, args.broadcaster, args.category, output_folder, args.delete)
  