import argparse
import json
import os
import subprocess
import math
import pytz
from pathlib import Path
from datetime import datetime, timedelta
from util.mediacms import MediaCMS_API
from luscioustwitch import *

FONT_SIZE=36

def get_clip_true_time(twitch_api, clip_info):
  if clip_info['video_id'] != '':
    video_info = twitch_api.get_video(clip_info['video_id'])
    offset = int(clip_info['vod_offset'])
    vod_start = datetime.strptime(video_info['created_at'], TWITCH_API_TIME_FORMAT)
    clip_time = vod_start + timedelta(seconds=offset)
    return clip_time
  else:
    return datetime.strptime(clip_info['created_at'], TWITCH_API_TIME_FORMAT)
    
if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--start', "-s", default="2022-12-01T00:00:01Z", help="Start of clip search")
  parser.add_argument('--end', "-e", default="2022-12-31T12:59:59Z", help="End of clip search")
  parser.add_argument('--buffer', '-b', default=8, type=int, help="Number of hours before/after period to consider")
  parser.add_argument('--stream', default="", help="Limit vids to one stream. This should be the video ID of the stream.")
  parser.add_argument('--channel', '-c', default="itswill", help="Twitch channel name")
  parser.add_argument('--max', "-m", default=20, type=int, help="Max clips to compile into the video.")
  parser.add_argument('--secrets', '-p', default="./secrets.json", help="JSON file with credentials")
  parser.add_argument('--outfolder', '-f', default="./out/", help="Temporary folder for holding clips")
  parser.add_argument('--output', '-o', default="./output.mp4", help="Output file name")
  parser.add_argument('--chrono', action="store_true", help="sort the clips chronologically")
  parser.add_argument('--stats', action="store_true", help="compile statistics for the period")
  parser.add_argument('--text_duration', default=15.0, type=float, help="Duration of the clip info text.")
  parser.add_argument('--timezone', '-z', default="America/Los_Angeles", help="Timeozne for start/end timestamps.")
  
  args = parser.parse_args()
  
  local = pytz.timezone(args.timezone)
  
  with open(args.secrets) as cred_file:
    cred_data = json.load(cred_file)
    archive_api = MediaCMS_API(cred_data['MEDIACMS']['URL'], (cred_data['MEDIACMS']['USERNAME'], cred_data['MEDIACMS']['PASSWORD']))
    twitch_api = TwitchAPI(cred_data["TWITCH"])
    gql_api = TwitchGQL_API()

  user_id = twitch_api.get_user_id(args.channel)
  if user_id == "":
    print(f"Failed to find {args.channel} in Twitch directory.")
    exit -1
    
  if args.stream == "":
    start_datetime = local.localize(datetime.strptime(args.start, TWITCH_API_TIME_FORMAT), is_dst=None)
    buffered_start_datetime = start_datetime - timedelta(hours = args.buffer)
    end_datetime = local.localize(datetime.strptime(args.end, TWITCH_API_TIME_FORMAT), is_dst=None)
    buffered_end_datetime = end_datetime + timedelta(hours = args.buffer)
  else:
    video_info = twitch_api.get_video(args.stream)
    start_datetime = pytz.utc.localize(datetime.strptime(video_info["created_at"], TWITCH_API_TIME_FORMAT), is_dst=None).astimezone(local)
    buffered_start_datetime = start_datetime
    durstr = video_info['duration']
    durdt = datetime.strptime(durstr, "%Hh%Mm%Ss") if 'h' in durstr else datetime.strptime(durstr, "%Mm%Ss") if 'm' in durstr else datetime.strptime(durstr, "%Ss")
    duration = timedelta(hours=durdt.hour, minutes=durdt.minute, seconds=durdt.second)
    end_datetime = start_datetime + duration
    buffered_end_datetime = end_datetime
    
  print(f"Searching for clips between {start_datetime.strftime(TWITCH_API_TIME_FORMAT)} and {end_datetime.strftime(TWITCH_API_TIME_FORMAT)}")

  out_path = Path(args.outfolder)
  if not os.path.exists(out_path):
    os.makedirs(out_path, exist_ok = True)
  
  stats = {}
  stats['clips']  = { 'list': [] }
  stats['videos'] = { 'list': []}
  stats['chat']   = { 'list': [] }

  num_clips = 0
  video_clips = []
  after = ""
  continue_fetching = True
  continue_adding = True
  clip_params = {
    "first": 5,
    "broadcaster_id": user_id,
    "started_at": buffered_start_datetime.astimezone(pytz.utc).strftime(TWITCH_API_TIME_FORMAT),
    "ended_at": buffered_end_datetime.astimezone(pytz.utc).strftime(TWITCH_API_TIME_FORMAT)
  }
  while continue_fetching:
    clips, cursor = twitch_api.get_clips(params=clip_params)

    if cursor != "":
      clip_params["after"] = cursor
    else:
      continue_fetching = False

    for clip in clips:
      views = int(clip["view_count"])
      clip_date = pytz.utc.localize(get_clip_true_time(twitch_api, clip), is_dst=None).astimezone(local)
      
      if not (buffered_start_datetime < clip_date < buffered_end_datetime):
        print("Clip not in range: ", clip["title"], clip_date.strftime(TWITCH_API_TIME_FORMAT))
        continue

      add_clip = continue_adding
      if continue_adding:
        for c in video_clips:
          if (clip["video_id"] == '' or clip["vod_offset"] == None or c[2]["video_id"] == '' or c[2]["vod_offset"] == None):
            if abs(c[0] - clip_date).total_seconds() < 90:
              print(f"Skipping \"{clip['title']}\" because \"{c[2]['title']}\" was already included.")
              add_clip = False
          # check if clips are from the same day and within 90 seconds of each other.
          elif (c[2]["video_id"] == clip["video_id"]) and (abs(int(c[2]["vod_offset"]) - int(clip["vod_offset"])) < 90):
            print(f"Skipping \"{clip['title']}\" because \"{c[2]['title']}\" was already included.")
            add_clip = False
        
      stats['clips']['list'].append(clip)
      if add_clip:
        video_clips.append((clip_date, views, clip))
        num_clips += 1

      if num_clips >= args.max:
        if not args.stats:
          continue_fetching = False
          break
        else:
          continue_adding = False
      if views < 5:
        continue_fetching = False
        break
      
  print(f"Got {len(video_clips)} clips.")

  drawtext_cmds = []
  start_time = 0
  
  runescape_font_path = os.path.abspath("./runescape_uf.ttf")

  os.chdir(out_path)

  if (args.chrono):
    video_clips.sort(key=lambda a: a[0])
  else:
    video_clips.sort(key=lambda a: a[1])
      
  if args.stats:
    video_params = {
      "user_id": user_id,
      "period": "all",
      "sort": "time",
      "type": "archive"
    }
    print("Getting all videos on channel.")
    videos = twitch_api.get_all_videos(video_params)
    
    for video in videos:
      vod_date = pytz.utc.localize(datetime.strptime(video['published_at'], TWITCH_API_TIME_FORMAT), is_dst=None).astimezone(local)
      
      if vod_date > buffered_start_datetime and vod_date < buffered_end_datetime:
        stats['videos']['list'].append(video)
        print(f"Fetching chat for vod {video['id']} - \"{video['title']}\"")
        vid_chat = gql_api.get_chat_messages(video['id'])
        stats['chat']['list'].extend(vid_chat)
        
    stats['clips']['count']  = len(stats['clips']['list'])
    stats['videos']['count'] = len(stats['videos']['list'])
    stats['chat']['count']   = len(stats['chat']['list'])
    
    stats['clips']['creators'] = { 'top': [], 'dict': {} }
    stats['chat']['chatters'] = { 'top': [], 'dict': {} }
    
    for clip in stats['clips']['list']:
      creator = clip['creator_name']
      if creator not in stats['clips']['creators']['dict']:
        stats['clips']['creators']['dict'][creator] = 1
      else:
        stats['clips']['creators']['dict'][creator] += 1
    
    stats['clips']['creators']['top'] = sorted(stats['clips']['creators']['dict'].items(), key=lambda c: c[1], reverse=True)
    
    for message in stats['chat']['list']:
      try:
        commenter = message['commenter']['displayName']
      except:
        continue
      if commenter not in stats['chat']['chatters']['dict']:
        stats['chat']['chatters']['dict'][commenter] = 1
      else:
        stats['chat']['chatters']['dict'][commenter] += 1
        
    stats['chat']['chatters']['top'] = sorted(stats['chat']['chatters']['dict'].items(), key=lambda c: c[1], reverse=True)
    
    with open("./clips.json", 'w') as clipsfile:
      clipsfile.write(json.dumps(stats['clips'], indent=2))
    with open("./videos.json", 'w') as videosfile:
      videosfile.write(json.dumps(stats['videos'], indent=2))
    with open("./chat.json", 'w') as chatfile:
      chatfile.write(json.dumps(stats['chat'], indent=2))

  if os.path.exists("./temp.mp4"):
    os.remove("./temp.mp4")

  with open("./concat.txt", 'w') as concatfile:
    with open("./desc.txt", 'w', encoding = "utf-8") as descfile:
      descfile.write(f"Top clips from {start_datetime.strftime('%Y-%m-%d')} until {end_datetime.strftime('%Y-%m-%d')}.\n\nCompiled by lusciousdev.\n\n\nClips: \n")
      for i in range(0, len(video_clips)):
        clip = video_clips[i][2]
        file_name = "{id}.mp4".format(**clip)
        if not os.path.exists(file_name):
          print(f"Downloading {clip['id']}.")
          gql_api.download_clip(clip['id'], "./temp.mp4")

          print(f"Converting {clip['id']} to 720p h264.")
          o = subprocess.run(["ffmpeg", "-y", "-i", "./temp.mp4", "-c:v", "libx264", "-preset", "fast", "-vf", "scale=1280:720", './temp2.mp4'], capture_output = True)
          
          name_format = f"#{len(video_clips) - i} - {{title}} - clipped by {{creator_name}}"
          if args.chrono:
            name_format = f"{{title}} - clipped by {{creator_name}}"

          clip_title = name_format.format(**clip).replace(":", "\\:").replace("'", "")
          clip_views = "{view_count} views".format(**clip)
          clip_date  = "{clip_date}".format(clip_date=video_clips[i][0].strftime("%Y-%m-%d"))
          
          text_start_time = 0
          text_end_time = math.floor(min(args.text_duration, float(clip['duration'])))
          
          runescape_rel_path = os.path.relpath(runescape_font_path).replace('\\', '/')
          drawtext_cmd = f"drawtext=fontfile='{runescape_rel_path}':text='{clip_title}':fontcolor=yellow:fontsize={FONT_SIZE}:box=1:boxcolor=black@0.5:boxborderw=5:x=20:y=20:enable='between(t,{text_start_time},{text_end_time})',drawtext=fontfile='{runescape_rel_path}':text='{clip_views}':fontcolor=yellow:fontsize={FONT_SIZE}:box=1:boxcolor=black@0.7:boxborderw=5:x=20:y=h-th-20:enable='between(t,{text_start_time},{text_end_time})',drawtext=fontfile='{runescape_rel_path}':text='{clip_date}':fontcolor=yellow:fontsize={FONT_SIZE}:box=1:boxcolor=black@0.7:boxborderw=5:x=w-tw-20:y=h-th-20:enable='between(t,{text_start_time},{text_end_time})'"
        
          print("Adding text to video.")
          o = subprocess.run(['ffmpeg', "-y", "-i", "./temp2.mp4", "-vf", drawtext_cmd, "./temp3.mp4"], capture_output = True)

          os.remove("./temp.mp4")
          os.remove("./temp2.mp4")
          os.rename("./temp3.mp4", file_name)
        else:
          print(f"{clip['id']} already downloaded.")

        try:
          concatfile.write(f"file {file_name}\n")
          descfile.write(f"\"{clip['title']}\"\nhttps://clips.twitch.tv/{clip['id']}\n")
        except:
          print(f"Failed to write \"\"{clip['title']}\"\nhttps://clips.twitch.tv/{clip['id']}\" to file.")

  print("Concatenating all clips.")
  o = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-i", "concat.txt", "-c", "copy", args.output], capture_output = True)