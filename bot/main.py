import os

from config import conf
from logger import log
from cmdClient.cmdClient import cmdClient

from BotData import BotData
from Timer import initialise

# Get the real location
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


# Load required data from configs
masters = [int(master.strip()) for master in conf['masters'].split(",")]
config = BotData(app="pomo", data_file="data/config_data.db")

# Initialise the client
client = cmdClient(prefix=conf['prefix'], owners=masters)
client.config = config

# Load the commands
client.load_dir(os.path.join(__location__, 'commands'))

# Add the post-event handlers
initialise(client)

# Log and execute!
log("Initial setup complete, logging in", context='SETUP')
client.run(conf['TOKEN'])
