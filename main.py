from urllib import request as urequest
from urllib import parse
from urllib import error as urlerror
from time import sleep
from datetime import datetime

import json, subprocess, os, sys, getopt

class TwitchDownloader():
    def __init__(self, username, quality, refresh_interval, ffmpath, uploader, remove_local):
        self.cid = "sspxioekgd3jbq5mxcyvil7bsigsg0"
        self.cs = "x7m6nejn7ob5y2mf596jxj2a01ycgg"
        self.token = self.get_token()

        self.refresh_interval = refresh_interval
        self.quality = quality
        self.username = username
        self.user_id = self.get_id()
        self.remove_local = remove_local

        self.ffmpeg_path = ffmpath
        self.uploader = uploader

        self.root_path = "/vods/"
        self.recorded_path = os.path.join(self.root_path, "recorded", self.username)
        self.processed_path = os.path.join(self.root_path, "processed", self.username)

        if(os.path.isdir(self.recorded_path) is False):
            os.makedirs(self.recorded_path)
        if(os.path.isdir(self.processed_path) is False):
            os.makedirs(self.processed_path)

        if(self.refresh_interval < 15):
            print("Check interval should not be lower than 15 seconds.")
            self.refresh_interval = 15
            print("System set check interval to 15 seconds.")

        try:
            video_list = [f for f in os.listdir(self.recorded_path) if os.path.isfile(os.path.join(self.recorded_path, f))]
            if(len(video_list) > 0):
                print('Fixing previously recorded files.')
            for f in video_list:
                recorded_filename = os.path.join(self.recorded_path, f)
                print('Fixing ' + recorded_filename + '.')
                try:
                    subprocess.call([self.ffmpeg_path, "-y", '-err_detect', 'ignore_err', '-i', recorded_filename, '-c', 'copy', os.path.join(self.processed_path,f)])
                    os.remove(recorded_filename)
                except Exception as e:
                    print(e)
        except Exception as e:
            print(e)

        print("Checking for", self.username, "every", self.refresh_interval, "seconds. Record with", self.quality, "quality.")
        self.check_loop()

    def get_status(self):
        header = {
            "Authorization": "Bearer " + self.token,
            "Client-Id": self.cid
        }

        url = "https://api.twitch.tv/helix/streams?user_id={uid}".format(
            uid = self.user_id
        )

        r = urequest.Request(url = url, headers = header, method = "GET")
        with urequest.urlopen(r) as res:
            result = json.loads(res.read().decode())
            #result = {'data': [], 'pagination': {}} if offline

            return not result["data"] == [], result

    def get_id(self):
        header = {
            "Authorization": "Bearer " + self.token,
            "Client-Id": self.cid
        }

        url = "https://api.twitch.tv/helix/users?login={un}".format(
            un = self.username
        )

        r = urequest.Request(url = url, headers = header, method = "GET")
        with urequest.urlopen(r) as res:
            result = json.loads(res.read().decode())
            return result["data"][0]["id"]

    def get_token(self):

        url = "https://id.twitch.tv/oauth2/token?client_id={cid}&client_secret={cs}&grant_type=client_credentials".format(
                cid = self.cid,
                cs = self.cs
        )

        r = urequest.Request(url = url, headers = {}, method = "POST")

        with urequest.urlopen(r) as res:
            result = json.loads(res.read().decode())
            return result["access_token"]

    def check_loop(self):
        while True:
            try:
                live, vod_info = self.get_status()
                upload_info = {
                    "title": "",
                    "desc": ""
                }

                if not live:
                    print("Offline, checking again in {} seconds.".format(self.refresh_interval))
                    sleep(self.refresh_interval)
                    continue

                print("{} is online, recording...".format(self.username))

                upload_info["title"] = vod_info["data"][0]["title"]
                upload_info["desc"] = "twitch.tv/{un}\n\n{time}".format(un=vod_info["data"][0]["user_name"], time=datetime.now().strftime("%b %d %Y"))

                for char in [" ", ":", "\\", "/"]:
                    vod_title = upload_info["title"].replace(char, "_")

                filename = vod_title + ".mp4"
                recorded_filename = os.path.join(self.recorded_path, filename)

                i = 1
                while os.path.exists(recorded_filename):
                    recorded_filename = os.path.join(self.recorded_path, "{}({}).mp4".format(vod_title, i))
                    i += 1

                subprocess.call(["streamlink", "twitch.tv/{}".format(self.username), "--twitch-disable-ads","-o", recorded_filename, "--default-stream", self.quality])

                print("{} offline, finished recording, fixing VOD.".format(self.username))

            except urlerror.HTTPError:
                print("Rerequesting token.")
                self.token = self.get_token()
                continue

            if(os.path.exists(recorded_filename)):
                try:
                    processed_filename = os.path.join(self.processed_path, filename)
                    subprocess.call([self.ffmpeg_path, '-err_detect', 'ignore_err', '-i', recorded_filename, '-c', 'copy', processed_filename])
                    os.remove(recorded_filename)
                except Exception as e:
                    print(e)
            else:
                print("Skip fixing. File not found.")

            self.uploader.upload(processed_filename, upload_info, self.remove_local)

            print("Wating for new stream.")


class YoutubeUploader():
    def __init__(self, uploaderpath, client_secrets):
        self.uploaderpath = uploaderpath
        self.cs = client_secrets

    def upload(self, vod, info, remove_local):
        print("Uploading vod...")

        if os.path.exists(vod):
            try:
                subprocess.call([self.uploaderpath, vod, "--privacy", "public", "--default-language", "en", "--default-audio-language", "en", "--title", info["title"], "--description", info["desc"], "--client-secrets", self.cs])

            except OSError:
                subprocess.call(["python", self.uploaderpath, vod, "--privacy", "public", "--default-language", "en", "--default-audio-language", "en", "--title", info["title"], "--description", info["desc"], "--client-secrets", self.cs])

            except Exception as e:
                print(e)

            if remove_local:
                print("Removing local file...")
                os.remove(vod)
                print("Vod removed.")
        else:
            print("File not found.")


def main(argv):
    options = {
        "username": "Tolomeo",
        "quality": "best",
        "refresh-interval": 30,
        "ffmpeg-path": "ffmpeg",
        "uploader-path": "youtube-uploader",
        "uploader-secrets": "./client_secrets.json",
        "remove-local": 1
    }

    manuals = {}

    try:
        opts = getopt.getopt(argv, "", ["username=", "quality=", "ffmpeg-path=", "uploader-path=", "refresh-interval=", "uploader-secrets=", "remove-local="])[0]

        for opt in opts:
            manuals[opt[0][2:]] = opt[1]
    except Exception as e:
        print(e)

    options.update(manuals)

    uploader = YoutubeUploader(
        uploaderpath = options["uploader-path"],
        client_secrets = options["uploader-secrets"]
    )
    downloader = TwitchDownloader(
        username = options["username"],
        quality = options["quality"],
        refresh_interval = options["refresh-interval"],
        ffmpath = options["ffmpeg-path"],
        remove_local = options["remove-local"],
        uploader = uploader
    )

if __name__ == '__main__':
    main(sys.argv[1:])
