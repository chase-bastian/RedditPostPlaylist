import logging
from config import reddit_client_secret, reddit_client_id, reddit_user_agent, spotify_client_secret, spotify_client_id
from APIs.reddit import get_top_lvl_comments
from APIs.spotify import create_list
import praw
import argparse
import re
import urllib
import json

# Basic configuration for logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the root logger level to DEBUG
    format='%(asctime)s - %(name)s %(lineno)d - %(levelname)s - %(message)s',  # Log format
    handlers=[
        logging.StreamHandler(),  # Console handler
        logging.FileHandler('log/app.log')  # File handler for 'app.log'
    ]
)

logger = logging.getLogger(__name__)

def get_songs(comments_raw):
    # TODO: Better algorithm to find song names from comments. LLM?
    songs = []
    for comment in comments_raw:
        if not hasattr(comment, "body"):  # "More Comments" has no body
            continue
        #print("2: " + comment.body[:25])
        txt = comment.body
        for line in txt.splitlines():
            songfound = False
            if line.lower().find("youtu") > -1:  # youtube link (easy)
                pos1 = line.find("[")
                pos2 = line.find("]")
                if pos1 > -1 and pos2 > -1:  # youtube link with description
                    if pos2 > pos1:  # CYA
                        titleYT = line[pos1 + 1:pos2]
                        if not titleYT.lower().find("youtu"):  # link was typed properly
                            songs.append(titleYT.strip())  # use link description
                            songfound = True
                if not songfound:  # just a youtube link, no description
                    for word in line.split():
                        if word.lower().startswith("youtu"):
                            titleYT = get_title_YT(word)
                            if titleYT is "":
                                continue
                            pos1 = titleYT.lower().find("(official")
                            if pos1 > 1:  # remove "(official video)" or similar
                                titleYT = titleYT[:pos1]
                            if len(titleYT) > 0:
                                songs.append(titleYT.strip())
            elif line.lower().find(" by ") > -1 or line.find("-") > -1:  # title by/- artist (commone)
                line = line.replace("”", "\"")
                line = line.replace("“", "\"")
                if line.lower().find(" by ") > -1:
                    delim = " by "
                else:
                    delim = " - "
                    if line.lower().count(delim) is 0:  # trim spaces
                        delim = delim.strip()
                split_line = re.split("[;,.]", line)  # in case multiple were listed
                for i in range(len(split_line)):
                    if len(split_line[i]) < 2:  # too short -> maybe was acronym?
                        split_line[i] = split_line[i - 1] + split_line[i]
                    elif split_line[i][:2] == "\" ":  # comma was potentially in title
                        split_line[i] = split_line[i - 1] + split_line[i]
                    elif split_line[i][:2] == "by":  # comma potentially between title/artist
                        split_line[i] = split_line[i - 1] + split_line[i]
                    if split_line[i].lower().find(" by ") > -1 or split_line[i].find("-") > -1:
                        if split_line[i].find(" by ") > -1:
                            split_line[i] = strip_extra(split_line[i], "by")
                        else:
                            split_line[i] = strip_extra(split_line[i], "-")
                        split_line[i] = split_line[i].replace("-", "")  # remove dashes
                        # split_line[i] = split_line[i].replace("\"", "") #remove quotes
                        songs.append(split_line[i].strip())
            else:  # weird/annoying format
                if len(line) > 100:
                    continue
                line = line.replace("-", "")  # remove dashes
                line = line.replace("\"", "")  # remove quotes
                pos1 = line.find(".")
                if pos1 > -1:
                    songs.append(line[:pos1].strip())
                else:
                    songs.append(line.strip())  # TODO: parse
    #print("3: " + str(len(songs)))
    songs = list(dict.fromkeys(songs))  # remove duplicates
    #print("4: " + str(len(songs)))
    return songs

def get_title_YT(vidlink):
    title = ""
    try:
        params = {"format": "json", "url": vidlink}
        url = "https://www.youtube.com/oembed"
        query_string = urllib.parse.urlencode(params)
        url = url + "?" + query_string
        with urllib.request.urlopen(url) as response:
            response_text = response.read()
            data = json.loads(response_text.decode())
            title = data['title']
    except Exception:
        pass
    return title


def strip_extra(text, delim):
    words = text.split()
    pos1 = 0
    for j in range(len(words)):  # find position of delim
        if words[j] is delim:
            pos1 = j
            break
    if pos1 is 0:  # might be mashed against preceding/following word
        for j in range(len(words)):
            if words[j].find(delim) > -1:
                pos1 = j
                break
    pos2 = 0
    j = pos1
    bOneFound = False
    if text.find("\"") > -1:
        while j < len(words):
            if words[j][-1] is "\"":  # word ends with quotes
                pos2 = j
                break
            j = j + 1
    if pos2 is 0:
        j = pos1  # reset j
        while j < len(words):  # find end of title/artist snippet
            if words[j].istitle():
                pos2 = j + 1
            elif len(words[j]) > 3:
                if bOneFound:  # not proper case
                    break
                else:
                    bOneFound = True
                    pos2 = j + 1
            j = j + 1
    if pos2 is 0:
        pos2 = len(words)
    j = pos1
    pos1 = 0
    if text.find("\"") > -1:
        while j > -1:
            if words[j][0] is "\"":
                pos1 = j
                break
            j = j - 1
    if pos1 is 0:
        while j > -1:  # find beginning of title/artist snippet
            if words[j].istitle():
                pos1 = j
            elif len(words[j]) > 3:
                break
            j = j - 1
    return " ".join(words[pos1:pos2])

if __name__ == "__main__":
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Accept a URL as an argument")

    # Add the URL argument
    parser.add_argument('url', type=str, help="The URL to process")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Access the URL from the arguments
    url = args.url

    #client_secret=""
    #client_id=""
    #version="0.0.1"
    #user_agent="post2play v: " + version + " by https://github.com/chase-bastian/RedditPostPlaylist"

    url = args.url
    if not args.url:
        url="https://www.reddit.com/r/Music/comments/1j1l0nz/saddest_songs_of_all_time/"

    reddit = praw.Reddit(
    client_id=reddit_client_id,
    client_secret=reddit_client_secret,
    user_agent=reddit_user_agent,
    )

    submission = reddit.submission(url=url)
    submission_id = reddit.submission(url=url).id
    comments = submission.comments.list()
    logger.debug(f"{comments=}")

    top_lvl_comments = get_top_lvl_comments(submission)
    logger.debug(f"{top_lvl_comments=}")

    songs = get_songs(top_lvl_comments)
    logger.debug(f"{songs=}")

    spotify_list = create_list(spotify_client_id, spotify_client_secret, "test Redditpost2playlist", submission_id, songs)
    logger.debug(f"{spotify_list=}")


