from fbchat import Client
from fbchat.models import *
from fbchat._message import Message

#example for fetching a User or group from a given URL
def getInfo(client :Client):

    print("Test")




if __name__ == "__main__":


    client = Client("sabbatinifrancois@gmail.com", "MyOwnPassword1!")
    theSearchUser = client.fetchUserInfo('100007160761754')