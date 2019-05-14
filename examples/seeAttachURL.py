from fbchat import Client
from fbchat.models import *

def getVideoURLs(client :Client):

    #Gets a list of users with the given name and uses the first user in the list
    users = client.searchForUsers('Testo Accounto')
    user = users[0]
    
    #Grabs the latest 10 messages in the thread with te given user and reverse the thread
    messages = client.fetchThreadMessages(thread_id=user.uid, limit=10)
    messages.reverse()

    #Loops through all the messages and their attachments and tries to fetch the video's URL
    #Also prints out the messages in the thread
    for message in messages:
        for attach in message.attachments:
            print(client.fetchVideoUrl(attach.uid))
        print(message.text)

def getImageURLs(client :Client):

    #Gets a list of users with the given name and uses the first user in the list
    users = client.searchForUsers('Testo Accounto')
    user = users[0]
    
    #Grabs the latest 10 messages in the thread with te given user and reverse the thread
    messages = client.fetchThreadMessages(thread_id=user.uid, limit=10)
    messages.reverse()

    #Loops through all the messages and their attachments and tries to fetch the image's URL
    #Also prints out the messages in the thread
    for message in messages:
        for attach in message.attachments:
            print(client.fetchImageUrl(attach.uid))
        print(message.text)

def getJSONs(client :Client):

    #Gets a list of users with the given name and uses the first user in the list
    users = client.searchForUsers('Testo Accounto')
    user = users[0]
    
    #Grabs the latest 10 messages in the thread with te given user and reverse the thread
    messages = client.fetchThreadMessages(thread_id=user.uid, limit=10)
    messages.reverse()

    #Loops through all the messages and their attachments and tries to fetch the JSON file associated with the attachments
    #Also prints out the messages in the thread
    for message in messages:
        for attach in message.attachments:
            print(client.fetchJSON(attach.uid))
        print(message.text)


def main():
    client = Client("sadm161@live.com", "Bravo127$")
    getVideoURLs(client)
    getImageURLs(client)
    getJSONs(client)
    print("EOF")

if __name__ == "__main__":
    main()