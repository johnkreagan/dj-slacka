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

from models import User, UserSchema, UserMapping, Track, PlayedTracks, LikedTracks

__spibot__ = Spotibot(os.environ["SLACK_API_TOKEN"])

@app.route("/user", methods=["GET"])
def get_user():
    all_users = User.query.all()
    result = users_schema.dump(all_users)
    return jsonify(result.data)

@app.route("/nowplaying", methods=["GET"])
def get_nowplaying():
    tunes = get_tunes_detailed()
    app.logger.error("TUNES: %s", tunes)
    jsoned = jsonify(tunes)
    app.logger.error("JSON: %s", jsoned)
    return jsoned

@app.route("/authdjrobot", methods=["POST"])
def authorizeDjRobot():
    slack_request = request.get_json()
    if "challenge" in slack_request:
        return(slack_request["challenge"])
    elif "event" in slack_request:
        event = slack_request["event"]
        return(handle_event(event))

@app.route("/comment", methods=["POST"])
def update_track_comment():
    comment = request.POST['comment']
    track_id = request.POST['track_idf']
    comment_track(track_id, comment)
    return jsonify("Success")

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
    app.logger.error("access: %s", access_token, refresh_token)
    if access_token and refresh_token:
        r = __spibot__.get_user_info(access_token)
        if r:
            username = r['id']
            name = r['display_name']
            u = User.query.filter_by(spotify_id=username).first()
            if (u is None):
                user_mapping = UserMapping.query.filter_by(spotify_user_name=name).first()
                if user_mapping is None:
                    return(jsonify("Incorrect spotify username passed in"))
                u = User(username, name, access_token, refresh_token, user_mapping.slack_user_name)
            else:
                u.access_token = access_token
            db.session.add(u)
            db.session.commit()
            return(jsonify("success!"))
    return(jsonify("error adding new user"))

@app.route("/rate/", methods=["GET"])
def rate():
    track_id = request.args.get('track_id', default = -1, type = int)
    app.logger.error("track_id: %s", track_id)
    
    return rate_track(track_id)


@app.route("/unlike/", methods=["GET"])
def unlike():
    track_id = request.args.get('track_id', default = -1, type = int)
    app.logger.error("track_id: %s", track_id)
    
    return unlike_track(track_id)

@app.route("/mostLikedSongs/", methods=["GET"])
def most_liked_songs():
    allLikedSongs = LikedTracks.query.group_by('track_id')
    return jsonify(allLikedSongs)

def rate_track(track_id):
    app.logger.error("Rating track %s", track_id)
    if track_id:
        likedTrack = LikedTracks(track_id)
        db.session.add(likedTrack)
        db.session.commit()
        return(jsonify("success!"))

    return(jsonify("error liking track"))

def unlike_track(track_id):
    app.logger.error("Unlike track %s", track_id)
    if track_id:
        toDelete = LikedTracks.query.filter_by(track_id=track_id).order_by('timestamp').limit(1)
        if toDelete is not None:
            db.session.delete(toDelete)
            db.session.commit()
        return(jsonify("success!"))

    return(jsonify("error deleting liked track"))

def get_likes_for_song(track_id):
    LikedTracks.query.filter_by(track_id=track_id).first()




def comment_track(track_id, comment):
    app.logger.error("commenting on track %s %b", track_id, comment)
    if track_id:
        track_object = Track.query.filter_by(track_id=track_id).first()
        if track_object:
            track_object.comment = comment
            db.session.commit()
            return(jsonify("success!"))

    return(jsonify("error adding new user"))

def handle_event(event):
    event_text = event["text"]
    peer_dj = event["user"]
    channel = event["channel"]
    if "dj" in event_text:
        return handle_dj(channel, event_text, peer_dj)
    elif "shuffle" in event_text:
        return handle_shuffle(channel, event_text)
    elif "enable" in event_text:
        return handle_enable(peer_dj)
    elif "disable" in event_text:
        return handle_disable(peer_dj)
    elif "help" in event_text:
        return __spibot__.send_data_to_slack(channel, get_help_text(), "Help Message Sent")

    else:
        return request.make_response("invalid event", 500)


def handle_delete(peer_dj):
    u = User.query.filter_by(slack_user_name=peer_dj).first()
    return __spibot__.send_data_to_slack(peer_dj, "User " +peer_dj + " deleted",
                                         "Help Message Sent")


def handle_help(channel):
    return __spibot__.send_data_to_slack(channel, get_help_text(),
                                         "Help Message Sent")


def handle_disable(peer_dj):
    user = User.query.filter_by(slack_user_name=peer_dj).first()
    user.enabled = False
    db.session.commit()
    return __spibot__.send_data_to_slack(peer_dj, ("User %s", user.enabled),
                                         ("User %s", user.enabled))


def handle_enable(peer_dj):
    user = User.query.filter_by(slack_user_name=peer_dj).first()
    user.enabled = True
    db.session.commit()
    return __spibot__.send_data_to_slack(peer_dj, ("User %s", user.enabled),
                                         ("User %s", user.enabled))


def handle_shuffle(channel, event_text):
    membersInChannel = []
    filterUsers = False
    if "channel" in event_text:
        membersInChannel = __spibot__.get_members_in_channel(channel)
        app.logger.error("members: %s channel: %s", membersInChannel, channel)
        filterUsers = True
    return __spibot__.send_data_to_slack(channel, get_tunes(membersInChannel,
                                                            filterUsers),
                                         "Songs Fetched")


def handle_dj(channel, event_text, peer_dj):
    user_name = (' '.join((event_text.split())[3:])).strip()
    if not user_name:
        return __spibot__.send_data_to_slack(channel, get_help_text(), "Help Message Sent")
    app.logger.error("user_name: %s peer_dj: %s", user_name, peer_dj)
    u_mapping = UserMapping.query.filter_by(slack_user_name=peer_dj).first()
    if "new dj" in event_text:
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
    elif "update dj" in event_text:
        if u_mapping is not None and u_mapping.spotify_user_name != user_name:
            u_mapping.spotify_user_name = user_name
            db.session.commit()
            return __spibot__.send_data_to_slack(peer_dj, "Spotify user updated", "updated")
        return __spibot__.send_data_to_slack(peer_dj, "Error occurred", "Error")


def get_random_fake_song():
    fileKey = random.randint(0,3)
    with open('sampleResponses/{}.json'.format(fileKey), 'r') as file:
        return json.loads(file.read())

def get_help_text():
    helpText = "-`@DJ SLACKA new dj <spotify name>` - create a user, use  example: `@DJ SLACKA new dj Camillionaire` \n"
    helpText += "-`@DJ SLACKA shuffle` - list of songs currently playing\n"
    helpText += "-`@DJ SLACKA shuffle channel` - list of songs currently playing filtered by users in the channel\n"
    helpText += "-`@DJ SLACKA update dj <spotify name>` - if you made a typo when trying to sign up originally\n"
    helpText += "-`@DJ SLACKA enable` - to let people know what you're listening to\n"
    helpText += "-`@DJ SLACKA disable` - listening to a NSFW playlist? jump off the public viewing list\n"
    return helpText



def get_tunes(membersInChannel, toFilterUsers):
    songs = []

    allUsers = User.query.filter_by(enabled=True)
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

    matchingTrack = Track.query.filter_by(spotify_id=track['id']).first()

    if matchingTrack is None:
        matchingTrack = Track(track['name'], get_artists_string(track), track['id'], 0 , "")
        db.session.add(matchingTrack)
    db.session.commit()

    playedTrack = PlayedTracks(matchingTrack.id, user.id)
    db.session.add(playedTrack)
    db.session.commit()
    return matchingTrack.id

def filterUsers(users, membersToInclude):
    filteredUsers = []
    if membersToInclude == []:
        return users
    for user in users:
        if user.slack_user_name in membersToInclude:
            filteredUsers.append(user)
    return filteredUsers

def get_tunes_detailed():
    songs = []
    for user in User.query.all():
        try:
            track = __spibot__.get_currently_playing(user.oauth)
            app.logger.error("spibot track retrieved: %s added to db", track)
            if track:
                track = track['item']
                track_id = add_to_playlist(track, user, get_artists_string(track))
                app.logger.error("playlist track retrieved: %s added to db", track_id)
                songs.append({"user":user.name,"track":track,"track_id":track_id})
                app.logger.error("Added to songs")
        except SpotifyAuthTokenError:
            _renew_access_token(user)
            __spibot__.get_currently_playing(user.oauth)
    if not songs:
        app.logger.error("Songs is NOT")
        return { "error": "Its quiet...too quiet...get some music started g"}
    app.logger.error("Returning songs %s", songs)
    return songs

def get_artists_string(track):

    if not track['artists']:
        return ""
    track_info = ""
    for i in track['artists']:
        track_info += "%s, " %(i['name'])

    return track_info

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
