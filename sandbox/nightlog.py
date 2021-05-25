#! /usr/bin/python3

import sys
sys.path.append('..')

# from autolog.eso.tapquery import NightQuery
from autolog.eso.log import *
from autolog.eso.date import *

period = 106
telescope = 'ESO-2.2m'
cls = NightLog
rootdir = '.'
use_tap_cache = True 
use_log_cache = False
night = '2020-03-03'

if night == 'all':
    nights = period_nights(period, format='iso')
else:
    nights = [night]

for night in nights:
    log = NightLog.fetch(telescope, night, use_log_cache=True,
        use_tap_cache=True)
