from fbchat import Client
from fbchat import separate_messages
from fbchat.models import *


client = Client('alexpacheco@charter.net', 'Q5pKJ9buWQ6v')

client.send(client, Message("This is a test message for my COMP 490 project."), '1275720524')
message = client.fetchThreadMessages('1275720524', limit=1)
client.unsend(message[0].uid)

client.logout()
