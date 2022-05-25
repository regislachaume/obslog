#! /usr/bin/env python3.9

import sys
sys.path.append('..')

from autolog.eso.tapquery import NightQuery

import numpy as np

night = sys.argv[1]
telescope = 'ESO-2.2m'
query = NightQuery(telescope=telescope)
log1 = query.fetch(night=night, use_tap_cache=False)
