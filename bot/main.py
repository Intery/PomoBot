import os

from config import conf
from logger import log
from cmdClient.cmdClient import cmdClient

from Timer import timer_controlloop

# Get the real location
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


masters = [int(master.strip()) for master in conf['masters'].split(",")]
print(masters)

client = cmdClient(prefix=conf['prefix'], owners=masters)
client.load_dir(os.path.join(__location__, 'commands'))

client.add_after_event("ready", timer_controlloop)

log("Initial setup complete, logging in", context='SETUP')
client.run(conf['TOKEN'])
