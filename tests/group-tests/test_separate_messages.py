from fbchat import Client
from fbchat import separate_messages

testClient = Client('alexpacheco@charter.net', 'Q5pKJ9buWQ6v')


def test_separate_messages():
    sent_messages = separate_messages.get_sent_messages(testClient)
    received_messages = separate_messages.get_received_messages(testClient)
    for message_s in sent_messages:
        for message_r in received_messages:
            assert message_s.author != message_r.author


testClient.logout()
