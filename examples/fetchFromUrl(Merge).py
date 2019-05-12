from fbchat import Client
from fbchat.models import *
from fbchat._message import Message


''''
urlForUserNames =   https://www.facebook.com/dana.foote1/
                    https://www.facebook.com/tykel.charles.7?
                    https://www.facebook.com/joel.rapoza
                    https://www.facebook.com/profile.php?id=100007160761754
'''

#example for fetching a User or group from a given URL
def getFromUserUrl(theUserUrl:str):

    #for "profile.php?id="
    if(theUserUrl.find("id=") != -1):
        print("<ID=> RAN")

        url1 = theUserUrl.split("id=")[1]
        url2 = ""
        for digit in url1:
            if (not digit.isdigit()):
                url2 = url1.split(digit)[0]
                break

        print(url2)

    #Case for facebook.com/<nickname>
    #Or for   facebook.com/<nickname>/
    else:

        url1 = theUserUrl.split("facebook.com/")[1]
        url2 = ""

        if(url1.find("/") != -1):
            print("</Nickname/> RAN")
            url2 = url1.split("/")[0]
            print(url2)

        elif(url1.find("?") != -1):
            print("</Nickname?> RAN")
            url2 = url1.split("?")[0]
            print(url2)

        else:
            print("</Nickname> RAN")
            print(url1)

    print("Test")


if __name__ == "__main__":

    url = 'https://www.facebook.com/profile.php?id=100027031812020&lst=100007160761754%3A100027031812020%3A1557634229&sk=friends&source_ref=pb_friends_tl'
    url2 = 'https://www.facebook.com/tykel.charles.7?'
    url3 = 'https://www.facebook.com/dana.foote1/'
    url4 = 'https://www.facebook.com/joel.rapoza'
    url5 = 'https://www.facebook.com/joel.rapoza/about?lst=100007160761754%3A1257548836%3A1557634533'
    url6 = 'https://www.facebook.com/james.curley.182?fref=pymk'


    getFromUserUrl(url6)

    #client = Client("sabbatinifrancois@gmail.com", "MyOwnPassword1!")
    #theSearchUser = client.fetchUserInfo('10211230319734619')