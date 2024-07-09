import re
import requests

MEDIACMS_VIDEO_REGEX = re.compile("(https?\:\/\/[A-Za-z0-9\.]+)\/view\?m=(.*)")

class MediaCMS_API:
  base_url = ""
  auth = None

  def __init__(self, base_url, auth):
    self.base_url = base_url
    self.auth = auth
    
  def get_clips(self):
    api_url = f"{self.base_url}/api/v1/media"
    
    clip_data = []
    while True:
      resp = requests.get(url = api_url, auth = self.auth)
      
      if resp.status_code != 200:
        return clip_data
      
      resp_json = resp.json()
      
      clip_data.extend(resp_json['results'])
      
      if resp_json['next']:
        api_url = resp_json['next']
      else:
        return clip_data

  def get_clip_info(self, clip_id):
    api_url = f"{self.base_url}/api/v1/media/{clip_id}"
    
    resp = requests.get(
      url=api_url,
      auth=self.auth
    )
  
    return resp.json()

  def get_clip_thumbnail_raw(self, clip_id):
    info = self.get_clip_info(clip_id)

    thumbnail_partial_url = info['thumbnail_url']
    thumbnail_url = f"{self.base_url}{thumbnail_partial_url}"
    r = requests.get(thumbnail_url)

    return r.content

  def download_clip(self, clip_id, filename):
    info = self.get_clip_info(clip_id)
    media_url = info['original_media_url']
    full_url = f"{self.base_url}{media_url}"
    r = requests.get(full_url)
    with open(filename, 'wb') as outfile:
      outfile.write(r.content)
      return True
    return False

  def upload_clip(self, filepath, title, description):
    upload_url = f"{self.base_url}/api/v1/media"
    
    resp = requests.post(
        url=upload_url,
        files={'media_file': open(filepath, 'rb')},
        data={'title': title, 'description': description},
        auth=self.auth
    )
    
    return resp.json()
      
  def search(self, query):
    api_url = f"{self.base_url}/api/v1/search?q={query}"
    
    resp = requests.get(api_url, auth = self.auth)
    
    if resp.status_code == 200:
      return resp.json()
    else:
      raise Exception(f"Response {resp.status_code}: {resp.reason}")