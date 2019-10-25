from flask import Flask, request, jsonify
from flask_heroku import Heroku
from flask_cors import CORS
from spotibot_client import Spotibot, SpotifyAuthTokenError
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
import os
import random
import json


app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
hku = Heroku(app)
ma = Marshmallow(app)
db = SQLAlchemy(app)

from models import User, UserSchema, UserMapping, Playlist

__spibot__ = Spotibot(os.environ["SLACK_API_TOKEN"])

@app.route("/user", methods=["GET"])
def get_user():
    all_users = User.query.all()
    result = users_schema.dump(all_users)
    return jsonify(result.data)

@app.route("/nowplaying", methods=["GET"])
def get_nowplaying():
    return jsonify(get_tunes_detailed())

@app.route("/authdjrobot", methods=["POST"])
def authorizeDjRobot():
    slack_request = request.get_json()
    if "challenge" in slack_request:
        return(slack_request["challenge"])
    elif "event" in slack_request:
        event = slack_request["event"]
        return(handle_event(event))

@app.route("/", methods=["GET"])
def get_response_from_spotty():
    code = request.values['code']
    access, refresh =__spibot__.parse_spotify_response(code)
    return(__create_user__(access, refresh))

@app.route("/authorizeme", methods=["GET", "POST"])
def get_authorization_token():
  if request.method == 'GET':
      return(jsonify("Authorize here: %s ", __spibot__.get_authorize_url()))
  else:
      return(jsonify("Error"))

def __create_user__(access_token, refresh_token):
    app.logger.error("access: %s refresh: %s", access_token, refresh_token)
    if access_token and refresh_token:
        r = __spibot__.get_user_info(access_token)
        if r:
            username = r['id']
            name = r['display_name']
            u = User.query.filter_by(spotify_id=username).first()
            if (u is None):
                user_mapping = UserMapping.query.filter_by(spotify_user_name=name).first()
                u = User(username, name, access_token, refresh_token, user_mapping.slack_user_name)
            else:
                u.access_token = access_token
            db.session.add(u)
            db.session.commit()
            return(jsonify("success!"))
    return(jsonify("error adding new user"))

def handle_event(event):
    event_text = event["text"]
    peer_dj = event["user"]
    channel = event["channel"]
    if "new dj" in event_text:
        user_name = (' '.join((event_text.split())[3:])).strip()
        if not user_name:
            return __spibot__.send_data_to_slack(channel, get_help_text(), "Help Message Sent")
        app.logger.error("user_name: %s peer_dj: %s", user_name, peer_dj)
        u_mapping = UserMapping.query.filter_by(slack_user_name=peer_dj).first()
        if u_mapping is None:
            u_mapping = UserMapping(peer_dj, user_name)
            db.session.add(u_mapping)
            db.session.commit()
            app.logger.error("u_mapping: %s added to db", u_mapping)
        elif u_mapping.spotify_user_name != user_name:
            u_mapping.spotify_user_name = user_name
            db.session.commit()
            app.logger.error("updated the spotify user name to : %s ", u_mapping.spotify_user_name)
        return __spibot__.send_authorization_pm(peer_dj, channel)
    elif "shuffle" in event_text:
        membersInChannel = []
        filterUsers = False
        if "channel" in event_text:
            membersInChannel = __spibot__.get_members_in_channel(channel)
            app.logger.error("members: %s channel: %s", membersInChannel, channel)
            filterUsers = True
        return __spibot__.send_data_to_slack(channel, get_tunes(membersInChannel, filterUsers), "Songs Fetched")
    elif "enable" in event_text:
        user = UserMapping.query.filter_by(slack_user_name=peer_dj).first()
        user.enabled = True
        db.session.commit()
    elif "disable" in event_text:
        user = UserMapping.query.filter_by(slack_user_name=peer_dj).first()
        user.enabled = False
        db.session.commit()
    elif "help" in event_text:
        return __spibot__.send_data_to_slack(channel, get_help_text(), "Help Message Sent")
    elif "delete" in event_text:
        u = User.query.filter_by(slack_user_name=peer_dj).first()
    else:
        return requests.make_response("invalid event", 500)

def get_random_fake_song():
    fileKey = random.randint(0,3)
    with open('sampleResponses/{}.json'.format(fileKey), 'r') as file:
        return json.loads(file.read())

def get_help_text():
    helpText = "-create a user, use `@DJ SLACKA new dj <spotify name>` example: `@DJ SLACKA new dj Camillionaire`\n"
    helpText += "-list of songs currently playing, use `@DJ SLACKA shuffle`\n"
    helpText += "-`@DJ SLACKA delete` -  removes yourself from our app\n"
    helpText += "-`@DJ SLACKA update dj <spotify name>` - if you made a typo when trying to sign up originally\n"
    helpText += "-`@DJ SLACKA enable` - to let people know what you're listening to\n"
    helpText += "-`@DJ SLACKA disable` - listening to a NSFW playlist? jump off the public viewing list\n"
    return helpText



def get_tunes(membersInChannel, toFilterUsers):
    songs = []

    allUsers = User.query.all()
    if toFilterUsers:
        filteredUsers = filterUsers(allUsers, membersInChannel)
    else:
        filteredUsers = allUsers

    for theUser in filteredUsers:
        app.logger.error("filteredUsers: %s ", theUser.name)

    for user in filteredUsers:
        try:
            track = __spibot__.get_currently_playing(user.oauth)
            if track:
                track = track['item']
                track_info = ''
                for i in track['artists']:
                    track_info += "%s, " %(i['name'])
                track_info = track_info[:-2]
                add_to_playlist(track, user, track_info)
                track_info += ": %s" %(track['name'])
                songs.append("%s -> %s" %(user.name, track_info))

        except SpotifyAuthTokenError:
            _renew_access_token(user)
            __spibot__.get_currently_playing(user.oauth)
    if not songs:
        return "Its quiet...too quiet...get some music started g"
    return '\n'.join(songs)

def add_to_playlist(track, user, track_info):
    playlist = Playlist(track['name'], track_info, user.id)
    db.session.add(playlist)
    db.session.commit()
    app.logger.error("playlist: %s added to db", playlist)

def filterUsers(users, membersToInclude):
    filteredUsers = []
    if membersToInclude == []:
        return users
    for user in users:
        if user.slack_user_name in membersToInclude and user.enabled:
            filteredUsers.append(user)
    return filteredUsers

def get_tunes_detailed():
    songs = []
    for user in User.query.all():
        try:
            track = __spibot__.get_currently_playing(user.oauth)
            if track:
                songs.append({"user":user.name,"track":track})
        except SpotifyAuthTokenError:
            _renew_access_token(user)
            __spibot__.get_currently_playing(user.oauth)
    if not songs:
        return { "error": "Its quiet...too quiet...get some music started g"}
    return songs

def _renew_access_token(user):
    t = __spibot__.get_new_access_token(refresh_token=user.refresh_tok)
    user_tok = t['access_token']
    ref_tok = t['refresh_token']
    user.oauth = user_tok
    user.refresh_tok = ref_tok
    db.session.add(user)
    db.session.commit()
    return (user)

user_schema = UserSchema()
users_schema = UserSchema(many=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8888")
    app.config['DEBUG'] = True
