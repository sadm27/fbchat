from fbchat import Client
from fbchat import separate_messages
from fbchat import Credentials

test_client = Client(Credentials.username, Credentials.password)


def test_separate_messages():
    sent_messages = separate_messages.get_sent_messages(test_client)
    received_messages = separate_messages.get_received_messages(test_client)
    for message_s in sent_messages:
        assert message_s.author == test_client.uid  # sent messages were written by user
        for message_r in received_messages:
            assert message_s != message_r           # sent and received messages are not the same
    for message_r in received_messages:             # separate for loop so that it does not get checked extra times
        assert message_r.author != test_client.uid  # received messages were not written by user


test_client.logout()
