import os

from data import tables, data  # noqa
from meta import client, conf

import Timer  # noqa


# Get the real location
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


# Load the commands
client.load_dir(os.path.join(__location__, 'commands'))
client.load_dir(os.path.join(__location__, 'plugins'))
# TODO: Recursive plugin loader

# Initialise the timer
# TimerInterface(client, conf['session_store'])
client.initialise_modules()


@client.set_valid_prefixes
async def valid_prefixes(client, message):
    return (
        (tables.guilds.fetch_or_create(message.guild.id).prefix if message.guild else None) or client.prefix,
        '<@{}>'.format(client.user.id),
        '<@!{}>'.format(client.user.id),
    )


# Log and execute!
client.log("Initial setup complete, logging in", context='SETUP')
client.run(conf['TOKEN'])
