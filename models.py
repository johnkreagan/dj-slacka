from app import db, ma
import datetime

class User(db.Model):
  __tablename__ = 'users'

  id = db.Column(db.Integer, unique=True, primary_key=True)
  name = db.Column(db.String(256), unique=False)
  spotify_id = db.Column(db.String(64), unique=True)
  oauth = db.Column(db.String(256), unique=True)
  refresh_tok = db.Column(db.String(256), unique=True)
  slack_user_name = db.Column(db.String(256), unique=False)
  enabled = db.Column(db.Boolean, unique=False)

  def __init__(self, user_id, display_name, oauth_token, refresh_token, slack_user_name):
    self.spotify_id = user_id
    self.oauth = oauth_token
    self.refresh_tok = refresh_token
    self.name = display_name
    self.slack_user_name = slack_user_name
    self.enabled = True

  def __repre__(self):
    return 'spotify id: {}, slack_user_name : {} >'.format(self.spotify_id, self.slack_user_name)

class UserSchema(ma.Schema):
  class Meta:
    fields = ('spotify_id', 'id', 'name')

class UserMapping(db.Model):
  __tablename__ = 'user_mapping'
  slack_user_name = db.Column(db.String(256), unique=True , primary_key=True)
  spotify_user_name = db.Column(db.String(64), unique=True)

  def __init__(self, slack_user_name, spotify_user_name):
    self.slack_user_name = slack_user_name
    self.spotify_user_name = spotify_user_name

  def __repre__(self):
    return 'slack user name : {}, spotify user name : {}>'.format(self.slack_user_name, self.spotify_user_name)

class Playlist(db.Model):
  __tablename__ = 'playlist'

  id = db.Column(db.Integer, unique=True, primary_key=True)
  track_name = db.Column(db.String(1024))
  artist = db.Column(db.String(1024))
  user_id = db.Column(db.Integer, db.ForeignKey('users.id'),nullable=False)

  def __init__(self, track_name, artist, user_id):
    self.track_name = track_name
    self.artist = artist
    self.user_id = user_id

  def __repre__(self):
    return '{}, track details track_name : {}, artist: {}, user_id:{} >'.format(self.id, self.track_name, self.artist, self.user_id)

class Track(db.Model):
  __tablename__ = 'tracks'

  id = db.Column(db.Integer, unique=True, primary_key=True)
  spotify_id = db.Column(db.String(1024))
  track_name = db.Column(db.String(1024))
  artist = db.Column(db.String(1024))
  rating = db.Column(db.Integer, unique=False)
  comments = db.Column(db.Text)

  def __init__(self, track_name, artist, spotify_id, rating, comments):
    self.track_name = track_name
    self.artist = artist
    self.spotify_id = spotify_id
    self.rating = rating
    self.comments = comments

  def __repre__(self):
    return '{}, track details track_name : {}, artist: {}, spotify_id:{} >'.format(self.id, self.track_name, self.artist, self.spotify_id)

class PlayedTracks(db.Model):
  __tablename__ = 'played_tracks'

  id = db.Column(db.Integer, unique=True, primary_key=True)
  track_id = db.Column(db.Integer, db.ForeignKey('tracks.id'),nullable=False)
  user_id = db.Column(db.Integer, db.ForeignKey('users.id'),nullable=False)
  timestamp = db.Column(db.DateTime)

  def __init__(self, track_id, user_id):
    self.track_id = track_id
    self.user_id = user_id
    self.timestamp = datetime.datetime.utcnow

  def __repre__(self):
    return 'track played track_id : {}, user_id: {}, timestamp:{} >'.format(self.track_id, self.user_id, self.timestamp)

class LikedTracks(db.Model):
  __tablename__ = 'liked_tracks'

  id = db.Column(db.Integer, unique=True, primary_key=True)
  track_id = db.Column(db.Integer, db.ForeignKey('tracks.id'),nullable=False)
  timestamp = db.Column(db.DateTime)

  def __init__(self, track_id):
    self.track_id = track_id
    self.timestamp = datetime.datetime.utcnow

  def __repre__(self):
    return 'track like track_id :{}, timestamp:{} >'.format(self.track_id, self.timestamp)