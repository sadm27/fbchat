from fbchat import Client
from fbchat.models import *


def get_sent_messages(client: Client):
    return _get_messages(client, True)


def get_received_messages(client: Client):
    return _get_messages(client, False)


def print_single_thread(client: Client, thread_id):
    messages = client.fetchThreadMessages(thread_id, limit=30)
    thread_info = client.fetchThreadInfo(thread_id)
    interlocutor = thread_info[thread_id]
    _print_thread_messages(client, messages, interlocutor)


def print_all_threads(client: Client):
    threads = client.fetchThreadList()
    for thread in threads:
        messages = client.fetchThreadMessages(thread.uid, limit=30)
        if thread.type == ThreadType.USER:
            thread_info = client.fetchThreadInfo(thread.uid)
            interlocutor = thread_info[thread.uid]
            _print_thread_messages(client, messages, interlocutor)
        else:
            _print_thread_messages(client, messages, None)


def _get_messages(client: Client, sent: bool):
    threads = client.fetchThreadList()
    sent_messages = []
    received_messages = []
    for thread in threads:
        messages = client.fetchThreadMessages(thread.uid, limit=30)
        name = client.fetchUserInfo(client.uid)[client.uid].name
        user = client.searchForUsers(name)[0]
        messages.reverse()
        for message in messages:
            if user.uid == message.author:
                sent_messages.append(message)
            elif user.uid != message.author:
                received_messages.append(message)
    if sent:
        return sent_messages
    else:
        return received_messages


def _print_thread_messages(client: Client, messages, interlocutor):
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

