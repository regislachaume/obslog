#! /usr/bin/python3

import sys
sys.path.append('..')

# from autolog.eso.tapquery import NightQuery
from autolog.eso.nightlog import *
from autolog.eso.periodlog import *
from autolog.eso.date import *

period = 107
telescope = 'ESO-2.2m'
cls = NightLog
opts = dict(
    rootdir = '.',
    use_tap_cache = True,
    use_log_cache = True,
)

log = PeriodLog.fetch(telescope, period, **opts) 

#for log_type in ['log', 'target']:
#    log.save(log_type, format='html')
#    log.publish(log_type)

