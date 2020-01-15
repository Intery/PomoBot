import os
import configparser as cfgp

CONFFILE = "config/bot.conf"
SECTION = "GENERAL"

if not os.path.isfile(CONFFILE):
    with open(CONFFILE, 'a+') as configfile:
        configfile.write('')

config = cfgp.ConfigParser()
config.read(CONFFILE)

if SECTION not in config.sections():
    config[SECTION] = {}

conf = config[SECTION]
