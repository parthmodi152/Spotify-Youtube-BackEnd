import json
import os
import urllib

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import requests
# import youtube_dl
from ytmusicapi import YTMusic

from exceptions import ResponseException
from secrets import spotify_token, spotify_user_id

ytmusic = YTMusic()

class CreatePlaylist:
    def __init__(self):
        self.youtube_client = self.get_youtube_client()
        self.all_song_info = {}

    def get_youtube_client(self):
        """ Log Into Youtube, Copied from Youtube Data API """
        # Disable OAuthlib's HTTPS verification when running locally.
        # *DO NOT* leave this option enabled in production.
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = "client_secret.json"

        # Get credentials and create an API client
        scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, scopes)
        credentials = flow.run_console()

        # from the Youtube DATA API
        youtube_client = googleapiclient.discovery.build(
            api_service_name, api_version, credentials=credentials)

        return youtube_client

    def get_liked_videos(self):
        """Grab Our Liked Videos & Create A Dictionary Of Important Song Information"""
        request = self.youtube_client.videos().list(
            part="snippet,contentDetails,statistics",
            myRating="like"
        )
        response = request.execute()
        # collect each video and get important information
        for item in response["items"]:
            video_title = item["snippet"]["title"]
            youtube_url = "https://www.youtube.com/watch?v={}".format(
                item["id"])

            # use ytmusicapi to collect song name & artist name

            search_results = ytmusic.search(video_title)
            j = len(search_results)
            i = 0
            # video_song_name = search_results[0]['title']
            # video_artist = search_results[0]['artist']
            while i < j:
                if search_results[i]['resultType'] == 'song':
                    song_name = search_results[i]['title']
                    artist = search_results[i]['artists'][0]['name']
                    break
                else:
                    i += 1

            while i < j:
                if search_results[i]['resultType'] == 'video':
                    video_song_name = search_results[i]['title']
                    video_artist = search_results[i]['artist']
                    break
                else:
                    i += 1

            if len(video_song_name) < len(song_name):
                song_name = video_song_name;
                artist = video_artist
            # # use youtube_dl to collect the song name & artist name
            # # video = youtube_dl.YoutubeDL({'nocheckcertificate': True}).extract_info(youtube_url, download=False)
            # # song_name = video["track"]
            # artist = video["artist"]

            if song_name is not None and artist is not None:
                # save all important info and skip any missing song and artist
                self.all_song_info[video_title] = {
                    "youtube_url": youtube_url,
                    "song_name": song_name,
                    "artist": artist,

                    # add the uri, easy to get song to put into playlist
                    "spotify_uri": self.get_spotify_uri(song_name, artist)

                }

    def create_playlist(self):

        """Checking if the playlist already exists"""
        query = "https://api.spotify.com/v1/users/{}/playlists".format(
            spotify_user_id)
        playlist = requests.post(
            query,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(spotify_token)
            }
        )
        playlist_json = playlist.json()
        out_file = open('spotify_playlist.json', "w")
        json.dump(playlist_json, out_file, indent=6)
        out_file.close()

        """Create A New Playlist"""
        request_body = json.dumps({
            "name": "Youtube Liked Vids",
            "description": "All Liked Youtube Videos",
            "public": True
        })

        query = "https://api.spotify.com/v1/users/{}/playlists".format(
            spotify_user_id)
        response = requests.post(
            query,
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(spotify_token)
            }
        )
        response_json = response.json()
        print(response_json['id'])
        # playlist id
        return response_json["id"]

    # def get_spotify_uri(self, song_name, artist):
    #     """Search For the Song"""
    #     query = "https://api.spotify.com/v1/search?query=track%3A{}+artist%3A{}&type=track&offset=0&limit=20".format(
    #         song_name,
    #         artist
    #     )
    #     print(query)
    #     response = requests.get(
    #         query,
    #         headers={
    #             "Content-Type": "application/json",
    #             "Authorization": "Bearer {}".format(spotify_token)
    #         }
    #     )
    #     response_json = response.json()
    #     out_file = open('spotify-response.json', "w")
    #     json.dump(response_json, out_file, indent=6)
    #     out_file.close()
    #     songs = response_json["tracks"]["items"]
    #
    #     # only use the first song
    #     uri = songs[0]["uri"]
    #
    #     return uri

    def get_spotify_uri(self, artist, track):
        query = urllib.parse.quote(f'{artist} {track}')
        url = f"https://api.spotify.com/v1/search?q={query}&type=track"
        response = requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {spotify_token}"
            }
        )
        response_json = response.json()

        results = response_json['tracks']['items']
        if results:
            # let's assume the first track in the list is the song we want
            uri = 'spotify:track:'+results[0]['id']
            print(uri)
            return uri
        else:
            raise Exception(f"No song found for {artist} = {track}")

    def add_song_to_playlist(self):
        """Add all liked songs into a new Spotify playlist"""
        # populate dictionary with our liked songs
        self.get_liked_videos()

        # collect all of uri
        uris = [info["spotify_uri"]
                for song, info in self.all_song_info.items()]

        # create a new playlist
        playlist_id = self.create_playlist()

        # add all songs into new playlist
        request_data = json.dumps(uris)

        query = "https://api.spotify.com/v1/playlists/{}/tracks".format(
            playlist_id)
        print(query)
        response = requests.post(
            query,
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(spotify_token)
            }
        )

        # check for valid response status
        if response.status_code != 200:
            raise ResponseException(response.status_code)

        response_json = response.json()
        return response_json


if __name__ == '__main__':
    cp = CreatePlaylist()
    cp.add_song_to_playlist()
