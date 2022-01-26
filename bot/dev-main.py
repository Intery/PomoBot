import logging
import meta

meta.logger.logger.setLevel(logging.DEBUG)
logging.getLogger("discord").setLevel(logging.INFO)

import main  # noqa
