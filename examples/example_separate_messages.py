from fbchat import Client
from fbchat import separate_messages
from fbchat.models import *


def print_author_ids(message_list):
    for message in message_list:
        print("Author:", message.author)


client = Client('alexpacheco@charter.net', 'Q5pKJ9buWQ6v')

print("------------------------")
print("Received Messages:")
print_author_ids(separate_messages.get_received_messages(client))
print("------------------------")
print("Sent Messages:")
print_author_ids(separate_messages.get_sent_messages(client))
print("------------------------")

client.logout()
