#! /usr/bin/env python3

import sys
sys.path.append('..')

# from autolog.eso.tapquery import NightQuery
from autolog.eso.allocation import Allocation

allocation = Allocation.read(telescope='ESO-2.2m', period=109)
allocation.save(format='html')
allocation.publish()
