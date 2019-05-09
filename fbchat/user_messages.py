from fbchat import Client
from fbchat.models import *


def print_thread_messages(client:Client, messages, interlocutor):
    name = client.fetchUserInfo(client.uid)[client.uid].name
    user = client.searchForUsers(name)[0]
    print("\n--------------------------------------------------\n")
    messages.reverse()
    for message in messages:
        if user.uid == message.author:
            print(user.name, ": ", message.text)
        elif interlocutor is not None and interlocutor.uid == message.author:
            print(interlocutor.name, ":", message.text)
        else:
            print("Group Member :", message.text)
    print("\n--------------------------------------------------\n")


def print_single_thread(client:Client, thread_id):
    messages = client.fetchThreadMessages(thread_id, limit=30)
    thread_info = client.fetchThreadInfo(thread_id)
    interlocutor = thread_info[thread_id]
    print_thread_messages(client, messages, interlocutor)


def print_all_threads(client:Client):
    threads = client.fetchThreadList()
    for thread in threads:
        messages = client.fetchThreadMessages(thread.uid, limit=30)
        if thread.type == ThreadType.USER:
            thread_info = client.fetchThreadInfo(thread.uid)
            interlocutor = thread_info[thread.uid]
            print_thread_messages(client, messages, interlocutor)
        else:
            print_thread_messages(client, messages, None)
