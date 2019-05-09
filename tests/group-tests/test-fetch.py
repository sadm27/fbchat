# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest

from os import path

import fbchat
from fbchat import Client
from fbchat.models import *

client = Client('sadm161@live.com', 'Bravo127$')

users = client.searchForUsers('Testo Accounto')


def test_fetch_image_url_png(client):
    client.sendLocalFiles([path.join(path.dirname(__file__), "resources", "image.png")])
    message, = client.fetchThreadMessages(limit=1)

    assert client.fetchImageUrl(message.attachments[0].uid)  == 9

def test_fetch_image_url_gif(client):
    client.sendLocalFiles([path.join(path.dirname(__file__), "resources", "image.gif")])
    message, = client.fetchThreadMessages(limit=1)

    assert client.fetchImageUrl(message.attachments[0].uid)

def test_fetch_video_url_mp4(client):
    client.sendLocalFiles([path.join(path.dirname(__file__), "resources", "video.mp4")])
    message, = client.fetchThreadMessages(limit=1)

    assert client.fetchVideoUrl(message.attachments[0].uid)

def test_fetch_video_url_webm(client):
    client.sendLocalFiles([path.join(path.dirname(__file__), "resources", "video.webm")])
    message, = client.fetchThreadMessages(limit=1)

    assert client.fetchVideoUrl(message.attachments[0].uid)