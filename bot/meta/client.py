from cmdClient.cmdClient import cmdClient

from .config import conf
from .logger import log


# Initialise client
masters = [int(master.strip()) for master in conf['masters'].split(",")]
client = cmdClient(prefix=conf['prefix'], owners=masters)
client.log = log
