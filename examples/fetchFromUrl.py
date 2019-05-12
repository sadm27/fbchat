from fbchat import Client
from fbchat.models import *
from fbchat._message import Message

#example for the fetching all the unread messages from a Group or User conversation
def getInfo(client :Client):

    #Retrieves the all the unread message Group and User conversation threads
    allTheUnreads = client.fetchUnread()

    #Goes through each one of the threads that have unread messages in it
    for allTheUnread in allTheUnreads:

        #Prints out all the Unread messages
        client.fetchUnreadFromThreadMessages(allTheUnread)


        for message_id in allTheUnread:

            client.markAsDelivered(allTheUnread, message_id)

            print ("Hello")





if __name__ == "__main__":

    client = Client("sabbatinifrancois@gmail.com", "MyOwnPassword1!")

    theSearchUser = client.fetchUserInfo('100007160761754')



   # getInfo(client)
