#! /usr/bin/env python3

import sys
sys.path.append('..')

# from autolog.eso.tapquery import NightQuery
from autolog.eso.nightlog import *
from autolog.eso.allocation import *
from autolog.eso.periodlog import *
from autolog.eso.date import *
from astropy.table import MaskedColumn

period = 110
telescope = 'ESO-2.2m'
cls = NightLog
opts = dict(
    rootdir = '.',
    use_tap_cache = False,
    use_log_cache = False,
)

log = PeriodLog.fetch(telescope, period, **opts) 

for log_type in ['log', 'target', 'report']:
   log.save(log_type=log_type, format='html')
   log.publish(log_type=log_type)
