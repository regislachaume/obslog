#! /usr/bin/python3

import sys
sys.path.append('..')

# from autolog.eso.tapquery import NightQuery
from autolog.eso.allocation import Allocation

allocation = Allocation.read(telescope='ESO-2.2m', period=104)
allocation = allocation.group_by(['TAC'])
allocation.save_as_html()
allocation.publish()
