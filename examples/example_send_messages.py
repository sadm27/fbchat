from fbchat import Client
from fbchat.models import *
import time
from fbchat import Credentials

client = Client(Credentials.username, Credentials.password)

client.wave(thread_id='1275720524', thread_type=ThreadType.USER)
client.send(client, Message("This is a test message for my COMP 490 project."), '1275720524')
client.send(client, Message("This message will be removed."), '1275720524')
end_time = time.time() + 10     # 10 seconds until message is removed
while time.time() <= end_time:
    x = 1   # wait
message = client.fetchThreadMessages('1275720524', limit=1)
client.unsend(message[0].uid)

client.logout()
