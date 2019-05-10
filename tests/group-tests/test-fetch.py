# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest

import fbchat
from fbchat import Client
from fbchat.models import *

client = Client('sadm161@live.com', 'Bravo127$')

"""
Test file for testing fetchImageUrl and fetchVideoUrl

:also test the refactoring of these fetch functions from _client.py to _fetcher.py
:uses my FB account and message thread for testing
:grabs the last four messages from Testo Accounto and checks their extentions
"""

def test_fetch_image_url_png():
    users = client.searchForUsers('Testo Accounto')
    user = users[0]

    messages = client.fetchThreadMessages(thread_id=user.uid, limit=4)
    messages.reverse()
    attach = messages[3].attachments[0]

    assert ".png" in client.fetchImageUrl(attach.uid) 


def test_fetch_image_url_jpg():
    users = client.searchForUsers('Testo Accounto')
    user = users[0]

    messages = client.fetchThreadMessages(thread_id=user.uid, limit=4)
    messages.reverse()
    attach = messages[2].attachments[0]

    assert ".jpg" in client.fetchImageUrl(attach.uid)



def test_fetch_video_url_mp4():
    users = client.searchForUsers('Testo Accounto')
    user = users[0]

    messages = client.fetchThreadMessages(thread_id=user.uid, limit=4)
    messages.reverse()
    attach = messages[1].attachments[0]

    assert ".mp4" in client.fetchVideoUrl(attach.uid)