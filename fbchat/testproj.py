from fbchat import Client
from fbchat import user_messages
from fbchat.models import *


client = Client('alexpacheco@charter.net', 'Jfp5Js9BDjs7')

users = client.searchForUsers('Alex Pacheco')
user = users[0]

print("User's ID: {}".format(user.uid))
print("User's name: {}".format(user.name))
print("User's profile picture url: {}".format(user.photo))
print("User's main url: {}".format(user.url))

#user_messages.print_all_threads(client)
#thread1 = client.fetchThreadList()[0]
#user_messages.print_single_thread(client, thread1.uid)
