import argparse
import os
from datetime import datetime, timedelta
from luscioustwitch import *
import math
    
if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--secrets", default = './secrets.json', help = "File containing Twitch and MediaCMS credentials.")
  parser.add_argument('--start', "-s", default="2022-01-01T00:00:01Z", help="Start of clip search")
  parser.add_argument('--end', "-e", default="2022-12-31T12:59:59Z", help="End of clip search")
  parser.add_argument('--minimum', "-m", default=50, type=int, help="Minimum number of views for a clip to get downloaded")
  parser.add_argument('--broadcaster', '-b', default="itswill", help="Broadcaster name.")
  parser.add_argument('--find', '-f', help="Find clip with name")
  parser.add_argument('--user', '-u', help="Find clips by user")
  parser.add_argument('--category', '-c', help="Find clips in the category")
  
  args = parser.parse_args()
  
  start_datetime = datetime.strptime(args.start, TWITCH_API_TIME_FORMAT)
  end_datetime = datetime.strptime(args.end, TWITCH_API_TIME_FORMAT)
  
  with open(args.secrets, 'r') as cred_file:
    cred_json = json.load(cred_file)
    twitch_api = TwitchAPI(credentials = cred_json['TWITCH'])
    gql_api = TwitchGQL_API()
  
  broadcaster_id = twitch_api.get_user_id(args.broadcaster)

  clip_params = {
    "broadcaster_id": broadcaster_id,
    "started_at": start_datetime.strftime(TWITCH_API_TIME_FORMAT),
    "ended_at": end_datetime.strftime(TWITCH_API_TIME_FORMAT),
    "first": 50
  }
  
  category_id = None
  if args.category is not None:
    category_id = twitch_api.get_category_id(args.category)
    print(f"{args.category} - {category_id}")
    # clip_params["game_id"] = category_id
  
  clip_count = 0
  continue_fetching = True
  while continue_fetching:
    clips, cursor = twitch_api.get_clips(clip_params)

    if cursor != "":
      clip_params["after"] = cursor
    else:
      continue_fetching = False
    
    for clip in clips:
      if int(clip['view_count']) < args.minimum:
        continue_fetching = False
        break
      
      clip_file_name = "{view_count}_[[{id}]].mp4".format(**clip)
      
      clip_match = True
      
      if (args.find is not None) and (args.find.lower() not in clip['title'].lower()):
        clip_match = False
      
      if (args.user is not None) and (args.user.lower() not in clip['creator_name'].lower()):
        clip_match = False
        
      if (category_id is not None) and (category_id != clip['game_id']):
        clip_match = False
      
      if clip_match:
        clip_count += 1
        title = f"\"{clip['title']}\"".ljust(60 - int(math.log10(clip_count)))
        creator = f"by {clip['creator_name']}".ljust(25)
        views = f"({clip['view_count']} views)".ljust(15)
        # print(f"{title} {creator} https://clips.twitch.tv/{clip['id']} Views: {clip['view_count']} Date: {clip['created_at']})")
        print(f"{clip_count}. {title} {creator} {views} ({clip['created_at']}) https://clips.twitch.tv/{clip['id']}")
  
  print(f"Clip count: {clip_count}")
  