#! /usr/bin/python3

import sys
sys.path.append('..')

from autolog.eso import path
from autolog.eso.nightlog import NightLog

night = '2020-03-03'
telescope = 'ESO-2.2m'
opts = dict(
    use_tap_cache = True,
    use_log_cache = True,
)

log = NightLog.fetch(telescope, night, **opts) 
log.save(format='html')
log.publish()
#
