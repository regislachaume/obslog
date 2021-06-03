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
night = '2021-03-03'

#self = NightQuery(telescope=telescope, rootdir=rootdir)
#telescope = self.telescope_names[0]
#filename = path.filename(telescope, night=night, name='tap',
#                rootdir=self.rootdir, makedirs=True)
#cls = type(self)
#tab = Table.read(filename, format=self.TABLE_FORMAT)
#cls._fix_column_types(tab)
# if night == 'all':
#     nights = period_nights(period, format='iso')
# else:
#     nights = [night]

log = NightLog.fetch(telescope, night, use_log_cache=True,
        use_tap_cache=True)
log.save_as_html()
log.publish()
