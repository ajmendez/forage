# api -- some nice api like functions.
import os
import pwd
import grp
import json
import time
import client
import tarfile
import calendar
import requests
import StringIO
import numpy as np
from pprint import pprint
from datetime import datetime

RATELIMIT = 2400 # really this is 250 -- but lets not anger the gods.
URL = 'http://cloud.feedly.com/v3/'

# USERFILE = os.path.expanduser('~/data/feedly/user.json')
# READFILE = os.path.expanduser('~/data/feedly/read.json')
# SAVEDFILE = os.path.expanduser('~/data/feedly/saved.json')
DIRECTORY = os.path.expanduser('~/data/feedly/')
USERFILE = DIRECTORY + 'user.tar.gz'
READFILE = DIRECTORY + 'read.tar.gz'
SAVEDFILE = DIRECTORY + 'saved.tar.gz'




try:
    from pymendez import auth
    USERID, TOKEN = auth('feedly',['dev_ident','dev_token'])
except Exception as e:
    print e
    # print 'Enter userid and token from dev.feedly:'
    # USERID = input(' userid:')
    # TOKEN = input(' token:')
    USERID,TOKEN = None,None

def convert_time(timestamp):
  return datetime.fromtimestamp(timestamp/1000.0)




class Data(object):
  def __init__(self, filename, fcn=list):
    '''Setup a Data object that is saved to a filename.
    fcn is the base datatype that starts the object if one does not exist.
    filename should be xxx.json, or xxx.tar.gz 
    '''
    self.filename = filename
    self.fcn = fcn
    
  def __enter__(self, *args, **kwargs):
    '''With constructor -- asks user for confirmation if file
    does not exist -- I think this is a good thing.'''
    try:
      self.data = self.load()
    except Exception as e:
      self.data = self.fcn()
      print ' Failed to load: {}'.format(self.filename)
      print e
      isok = raw_input('Are you ok with this? [yes/no]: ')
      if 'y' not in isok.lower():
        raise
      # ensure that the directory exists
      dirname = os.path.dirname(self.filename)
      if not os.path.exists(dirname):
        os.makedirs(dirname)
    return self
  
  def __exit__(self, *args, **kwargs):
    '''save the file on exit'''
    self.save()
  
  def __len__(self):
    '''len() of object'''
    return len(self.data)
  
  def save(self):
    '''Save the file as a json.dump or a tarfile depending
    on the file ending'''
    if '.tar.gz' in self.filename:
      self.savegz()
    else:
      json.dump(self.data, open(self.filename,'w'), indent=2)
  
  def load(self):
    '''Load the file as a json file or a tar file.'''
    if '.tar.gz' in self.filename:
      return self.loadgz()
    else:
      return json.load(open(self.filename))
  
  def getname(self):
    '''get a nice file name to put within the tar file.'''
    return os.path.basename(self.filename).replace('.tar.gz','.json')
  
  def savegz(self):
    '''save the file within a gziped tar file'''
    with tarfile.open(self.filename, 'w:gz') as tar:
      fileobj = StringIO.StringIO()
      json.dump(self.data, fileobj, indent=2)
      fileobj.seek(0)
      tarinfo = tarfile.TarInfo(self.getname())
      tarinfo.size = fileobj.len
      tarinfo.mtime = calendar.timegm(time.gmtime())
      tarinfo.mode = int('0644', 8) # convert to octal
      tarinfo.uid = os.getuid()
      tarinfo.uname = pwd.getpwuid(tarinfo.uid)[0]
      tarinfo.gid = os.getgid()
      tarinfo.gname = grp.getgrgid(tarinfo.gid)[0]
      tar.addfile(tarinfo, fileobj)
  
  def loadgz(self):
    '''Load a json object out of a tar.'''
    with tarfile.open(self.filename, 'r:gz') as tar:
      return json.load(tar.extractfile(tar.getmember(self.getname())))
  
  def append(self, item):
    '''Append to the file'''
    self.data.append(item)
  
  def get(self, key):
    return [item[key] for item in self.data]
      


class Forage(object):
  def __init__(self, userid=USERID, token=TOKEN):
    self.userid = userid
    self.token = token
    self.ratelimit = 0
    self.headers = {}
    self.api = client.FeedlyClient(access_token=token, sandbox=False)
    
  
  def _get(self, url, **kwargs):
    '''Get the json of a url with some keywords
    keywords are passed into the requests.get command'''
    if self.ratelimit > RATELIMIT:
      pprint(self.headers)
      raise IOError('Rate Limited!')
    tmp = {'headers':{'Authorization':'OAuth {}'.format(self.token)}}
    tmp.update(kwargs)
    response = requests.get(URL + url, **tmp)
    
    # try to keep abreast of the rate limit
    try:
      self.headers = response.headers
      self.ratelimit = int(response.headers['x-ratelimit-count'])
    except:
      print self.headers
      pass
    return response.json()
  
  
  def get_profile(self):
    '''Get the user profile'''
    url = 'profile'
    return self._get(url)
  
  
  def get_feeds(self):
    '''Get a list of the subscriptions that the user has'''
    url = 'subscriptions'
    return self._get(url)
  
  
  def get_streams(self, streamid, **kwargs):
    '''Get the response json for a streamid.  extra args are 
    passed in a params.'''
    url = 'streams/contents'
    params = {'streamId':streamid, 'count':10000}
    params.update(kwargs)
    return self._get(url, params=params)
  
  
  def gen_streams(self, streamid, repeat=10, **kwargs):
    '''Generator of items from streamid call.
    
    Wrapper around the _get that handles the continuation key.
    
    repeat : number of times to repeat command. =None to go on and on.
    kwargs : passed to request params keyword
      this handles things like count, newerThan, ranked, and unreadOnly
      '''
    continuation = None
    while (repeat > 0) or (repeat is None):
      if continuation:
        kwargs['continuation'] = continuation
      
      data = self.get_streams(streamid, **kwargs)
      
      # yield an item
      for item in data['items']:
        yield item
      
      # continue down the tree unless there is no more.
      if 'continuation' not in data:
        break
      else:
        continuation = data['continuation']
      
      if repeat is not None:
        repeat -= 1
  
  
  def gen_read(self, **kwargs):
    '''generate all of the read articles of the subscribed feeds'''
    streamid = 'user/{}/tag/global.read'.format(self.userid)
    return self.gen_streams(streamid, **kwargs)
  
  
  def gen_saved(self, **kwargs):
    '''Generate all of the saved saved articles'''
    streamid = 'user/{}/tag/global.saved'.format(self.userid)
    return self.gen_streams(streamid, **kwargs)





if __name__ == '__main__':
    from pysurvey import util
    util.setup_stop()
    
    api = Forage()
    # pprint(api.get_profile())
    # pprint(api.get_feeds())
    # for x in api.gen_read(repeat=1):
    #   print convert_time(x.get('actionTimestamp',-1))
    #   # pprint(x)
    uids = []
    for entry in api.gen_saved(repeat=None, count=10000):
      uids.append(entry['id'])
      k = len(uids)
      if (k%10000) == 0:
        print k, len(np.unique(uids)), api.ratelimit
        print convert_time(entry['actionTimestamp'])
        pprint(entry)
    
    
    print 'Rate Limit: {}'.format(api.ratelimit)