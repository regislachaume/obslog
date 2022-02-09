#! /usr/bin/python3.9

import sys
sys.path.append('..')

from autolog.eso.schedule import Schedule

period = 109
telescope = 'ESO-2.2m'
schedule = Schedule.read(telescope=telescope, period=period)

schedule.save(format='html', overwrite=True)
schedule.publish()

support = schedule.shifts()

support.save(log_type='support', format='html', overwrite=True)
support.publish(log_type='support')
