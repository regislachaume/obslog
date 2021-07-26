#! /usr/bin/python3

import sys
sys.path.append('..')

from autolog.eso.schedule import Schedule

period = 107
telescope = 'ESO-2.2m'
schedule = Schedule.read(telescope=telescope, period=period)

schedule.save(format='html')
schedule.publish()
