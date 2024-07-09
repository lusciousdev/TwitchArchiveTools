from util.mediacms import MediaCMS_API
import json
import argparse

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--secrets", '-s', default = './secrets.json', help = "File containing Twitch and MediaCMS credentials.")
  parser.add_argument("--mediaurl", '-m', default = 'https://clips.itswill.org', help = "MediaCMS URL")
  
  args = parser.parse_args()
  
  with open(args.secrets, 'r') as cred_file:
    cred_json = json.load(cred_file)
    mediacms_api = MediaCMS_API(args.mediaurl, (cred_json['MEDIACMS']['USERNAME'], cred_json['MEDIACMS']['PASSWORD']))
    
  clips = mediacms_api.get_clips()
  print(f'Got {len(clips)} clips.')
  
  no_clip_id = open('./noclipid.txt', 'w')
  no_clip_count = 0
  
  for clip in clips:  
    if "clip" not in clip['description']:
      no_clip_count += 1
      print(f'Clip "{clip["title"]}" does not have a clip id in its description.')
      no_clip_id.write(clip['url'] + '\n')
      
  print(f'Found {no_clip_count} clips without clip id.')