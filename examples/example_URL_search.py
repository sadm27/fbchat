# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest

import fbchat
from fbchat import Client
from fbchat.models import *
from fbchat import Credentials


def test_User_URL_search_Name(client):
    
    userName = client.getFromUserUrl("https://www.facebook.com/testo.accounto.3150/friends?lst=1257548836%3A100035148553478%3A1557696307&source_ref=pb_friends_tl")
    users = client.searchForUsers(userName)
    u = users[0]

    print(u.uid)    #"100035148553478"
    print(u.name)   #"Testo Accounto"


def test_User_URL_search_ID(client):
    
    userID = client.getFromUserUrl("https://www.facebook.com/profile.php?id=100007160761754&lst=1257548836%3A100007160761754%3A1557627804&sk=about")
    user = client.fetchUserInfo(userID)

    print(user)

    print(user[userID].uid)    #"100007160761754"
    print(user[userID].name)   #"Sabbatini Francois"


def test_Group_URL_search_Name(client):
    
    groupName = client.getFromGroupUrl("https://www.facebook.com/groups/masstuning/about/")
    print(groupName)
    groups = client.searchForGroups(groupName)
    g = groups[0]

    print(g.uid)    #"183854084980854"
    print(g.name)   #"MassTuning"


def test_Group_URL_search_ID(client):
    
    GroupID = client.getFromGroupUrl("https://www.facebook.com/groups/12199253345/about/")
    group = client.fetchGroupInfo(GroupID)

    print(group.uid)    #"12199253345"
    print(group.name)   #"Tuning Alliance Crew"



def main():
    client = Client(Credentials.username, Credentials.password)
    #test_User_URL_search_Name(client)
    #test_User_URL_search_ID(client)
    test_Group_URL_search_Name(client)
    #test_Group_URL_search_ID(client)
    print("EOF")

if __name__ == "__main__":
    main()