#! /usr/bin/env python3

import sys
sys.path.append('..')

# from autolog.eso.tapquery import NightQuery
from autolog.eso.allocation import Allocation

period = 111
telescope = 'ESO-2.2m'
allocation = Allocation.read(telescope=telescope, period=period)
allocation.save(format='html')
allocation.publish()
