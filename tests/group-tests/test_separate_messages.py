from fbchat import Client
from fbchat import separate_messages

test_client = Client('alexpacheco@charter.net', 'Q5pKJ9buWQ6v')


def test_separate_messages():
    sent_messages = separate_messages.get_sent_messages(test_client)
    received_messages = separate_messages.get_received_messages(test_client)
    for message_s in sent_messages:
        assert message_s.author == test_client.uid      # sent messages were written by user
        for message_r in received_messages:
            assert message_s.author != message_r.author  # sent and received messages do not have same author
    for message_r in received_messages:                 # separate for loop so that it does not get checked extra times
        assert message_r.author != test_client.uid      # received messages were not written by user


test_client.logout()