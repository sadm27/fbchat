# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest

import fbchat
from fbchat import Client
from fbchat.models import *

client = Client('sadm161@live.com', 'Bravo127$')


def test_User_URL_search_Name():
    
    userName = client.getFromUserUrl("https://www.facebook.com/testo.accounto.3150/friends?lst=1257548836%3A100035148553478%3A1557696307&source_ref=pb_friends_tl")
    users = client.searchForUsers(userName)
    u = users[0]

    assert u.uid == "100035148553478"
    assert u.name == "Testo Accounto"


    def test_User_URL_search_ID():
    
    userID = client.getFromUserUrl("https://www.facebook.com/profile.php?id=100007160761754&lst=1257548836%3A100007160761754%3A1557627804&sk=about")
    user = client.fetchUserInfo(userID)

    assert user.uid == "100007160761754"
    assert user.name == "Sabbatini Francois"


    def test_Group_URL_search_Name():
    
    groupName = client.getFromGroupUrl("https://www.facebook.com/groups/masstuning/about/")
    groups = client.searchForGroups(groupName)
    g = groups[0]

    assert g.uid == "183854084980854"
    assert g.name == "MassTuning"


    def test_Group_URL_search_ID():
    
    GroupID = client.getFromGroupUrl("https://www.facebook.com/groups/12199253345/about/")
    group = client.fetchGroupInfo(GroupID)

    assert group.uid == "12199253345"
    assert group.name == "Tuning Alliance Crew"