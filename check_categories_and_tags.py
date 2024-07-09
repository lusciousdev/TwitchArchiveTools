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
  
  no_categories = open('./nocategories.txt', 'w')
  no_tags = open('./notags.txt', 'w')
  
  cat_count = 0
  tag_count = 0
  
  for clip in clips:
    clip_details = mediacms_api.get_clip_info(clip['friendly_token'])
    
    if len(clip_details['categories_info']) == 0:
      print(f'Clip "{clip_details["title"]}" does not have a category assigned.')
      no_categories.write(clip_details['url'] + '\n')
      cat_count += 1
      
    if len(clip_details['tags_info']) == 0:
      print(f'Clip "{clip_details["title"]}" does not have a tag assigned.')
      no_tags.write(clip_details['url'] + '\n')
      tag_count += 1
      
  print(f'Found {cat_count} clips withount a category and {tag_count} clips without tags.')