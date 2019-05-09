# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest

from os import path

import fbchat
from fbchat import Client
from fbchat.models import *

client = Client('sadm161@live.com', 'Bravo127$')

#users = client.searchForUsers('Testo Accounto')




def test_fetch_image_url_png():
    #client = Client('sadm161@live.com', 'Bravo127$')
    users = client.searchForUsers('Testo Accounto')
    user = users[0]

    messages = client.fetchThreadMessages(thread_id=user.uid, limit=4)
    messages.reverse()
    attach = messages[3].attachments[0]

    assert ".png" in client.fetchImageUrl(attach.uid) 


def test_fetch_image_url_jpg():
    #client = Client('sadm161@live.com', 'Bravo127$')
    users = client.searchForUsers('Testo Accounto')
    user = users[0]

    messages = client.fetchThreadMessages(thread_id=user.uid, limit=4)
    messages.reverse()
    attach = messages[2].attachments[0]

    assert ".jpg" in client.fetchImageUrl(attach.uid)



def test_fetch_video_url_mp4():
    #client = Client('sadm161@live.com', 'Bravo127$')
    users = client.searchForUsers('Testo Accounto')
    user = users[0]

    messages = client.fetchThreadMessages(thread_id=user.uid, limit=4)
    messages.reverse()
    attach = messages[1].attachments[0]

    assert ".mp4" in client.fetchVideoUrl(attach.uid)