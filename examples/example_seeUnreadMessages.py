from fbchat import Client
from fbchat.models import *
from fbchat import Credentials

#example for the fetching all the unread messages from a Group or User conversation
def getInfo(client :Client):

    #Retrieves the all the unread message Group and User conversation threads
    allTheUnreads = client.fetchUnread()

    #Goes through each one of the threads that have unread messages in it
    for allTheUnread in allTheUnreads:

        #Prints out all the Unread messages
        client.fetchUnreadFromThreadMessages(allTheUnread)

if __name__ == "__main__":

    client = Client(Credentials.username, Credentials.password)
    getInfo(client)
