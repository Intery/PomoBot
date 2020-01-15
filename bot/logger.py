import sys
import logging

from config import conf


# Setup the logger
LOGFILE = conf['logfile']
logger = logging.getLogger()
log_fmt = logging.Formatter(fmt='[{asctime}][{levelname:^8}] {message}', datefmt='%d/%m | %H:%M:%S', style='{')
file_handler = logging.FileHandler(filename=LOGFILE, encoding='utf-8', mode='a')
term_handler = logging.StreamHandler(sys.stdout)
file_handler.setFormatter(log_fmt)
term_handler.setFormatter(log_fmt)
logger.addHandler(file_handler)
logger.addHandler(term_handler)
logger.setLevel(logging.INFO)


def log(message, context="Global".center(18, '='), level=logging.INFO):
    for line in message.split('\n'):
        logger.log(level, '[{}] {}'.format(str(context).center(18, '='), line))
