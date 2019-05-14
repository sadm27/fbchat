from fbchat import Client
from fbchat import separate_messages
from fbchat import Credentials

def print_author_ids(message_list):
    for message in message_list:
        print("Author:", message.author)


client = Client(Credentials.username, Credentials.password)

print("------------------------")
print("Received Messages:")
print_author_ids(separate_messages.get_received_messages(client))
print("------------------------")
print("Sent Messages:")
print_author_ids(separate_messages.get_sent_messages(client))
print("------------------------")

print("\nThread #1275720524:")
separate_messages.print_single_thread(client, '1275720524')

client.logout()
