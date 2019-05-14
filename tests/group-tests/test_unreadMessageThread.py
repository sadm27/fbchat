import fbchat
from fbchat import Client
from fbchat.models import *
from fbchat._message import Message
from fbchat import Credentials

testClient = Client(Credentials.username, Credentials.password)

def test_fetchUnreadFromThreadMessages():

    allTheUnread = testClient.fetchUnread()

    assert isinstance(allTheUnread, list), 'allTheUnread object is not type of list'
    assert len(allTheUnread) > 0, 'There is no Unread Messages on your Facebook Messages, Make one.'

    #Checks for a thread message
    anUnreadMessage = testClient.fetchThreadMessages(allTheUnread[0])
    assert isinstance(anUnreadMessage[0], Message), 'anUnreadMessage is not a Message Type'

    theTestMessage = testClient.fetchUnreadFromThreadMessages(allTheUnread[0])
    assert theTestMessage == True, 'theTestMessage failed to print'
