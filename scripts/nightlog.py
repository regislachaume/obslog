#! /usr/bin/python3

import sys
sys.path.append('..')

from autolog.eso import path
from autolog.eso.nightlog import NightLog
from autolog.eso.allocation import Allocation

import warnings
warnings.filterwarnings('error', category=Warning)

import numpy as np

night = '2022-05-22'
telescope = 'ESO-2.2m'
opts = dict(
    use_tap_cache = False, 
    use_log_cache = False,
)

log = NightLog.fetch(telescope, night, **opts) 

log.save(format='html', overwrite=True)
log.publish()
