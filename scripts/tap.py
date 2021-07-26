#! /usr/bin/python3

import sys
sys.path.append('..')

from autolog.eso.tapquery import NightQuery

import numpy as np

night = '2021-01-01'
telescope = 'ESO-2.2m'
query = NightQuery(telescope=telescope)
log1 = query.fetch(night=night, use_tap_cache=False)
log2 = query.fetch(night=night, use_tap_cache=True)
