import argparse
from bs4 import BeautifulSoup
import random
import requests
import config
from ssl_util import SharedSSLAdapter
import re


def get_parser():
    parser = argparse.ArgumentParser(description="JableTV & MissAV Downloader — by ALOS")
    # store_true, not type=bool: argparse's bool("False") is truthy, so `--nogui False`
    # would wrongly enable it. store_true makes the mere presence of the flag mean True.
    parser.add_argument("--random", action='store_true',
                        help="Download a random recommended video")
    parser.add_argument("--url", type=str, default="",
                        help="Jable TV URL to download")
    parser.add_argument("--nogui", action='store_true',
                        help="Disable GUI mode")
    parser.add_argument(
        "-o", "--output", type=str, default="download", metavar="DIR",
        help="Output directory for downloads (default: ./download)")

    return parser


def av_recommand():
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = 'https://jable.tv/'
    try:
        with requests.Session() as session:
            session.mount('https://', SharedSSLAdapter())
            response = session.get(
                url, headers=headers, timeout=15,
                **config.proxy_request_kwargs())
            response.raise_for_status()
            web_content = response.content
    except Exception:
        return None
    # 得到繞過轉址後的 html
    soup = BeautifulSoup(web_content, 'html.parser')
    h6_tags = soup.find_all('h6', class_='title')
    av_list = re.findall(r'https[^"]+', str(h6_tags))
    if not av_list:              # site changed/blocked -> avoid random.choice([]) IndexError
        return None
    return random.choice(av_list)


# print(av_recommand())
