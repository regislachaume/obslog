#! /usr/bin/python3

import sys
sys.path.append('..')

# from autolog.eso.tapquery import NightQuery
from autolog.eso.log import *
from autolog.eso.date import *

period = 106
telescope = '2.2m'
cls = NightLog
rootdir = '.'
use_tap_cache = True 
use_log_cache = False
night = '2020-03-03'

filename = path.filename(telescope, night=night, name='log',
                rootdir=rootdir)
query = NightQuery(telescope=telescope, rootdir=rootdir)
log = query.fetch(night=night, use_tap_cache=use_tap_cache)
log.__class__ = cls

log.add_night_info()
log['tpl_seqno'].name = 'tpl_no'
log['tpl_expno'].name = 'exp_no'
log['pi_coi'].name = 'pi'
log.add_ephemeris()
log.average_conditions()
log.add_track_info()
log.add_exp_end()
log.add_ob_no()
log.add_tpl_end()
log.add_ob_boundaries()
log.fix_ob_boundaries()
log.fill_missing_templates()
log.fill_idle_rows()
log.add_time_accounting()

#if night == 'all':
#    nights = period_nights(period, format='iso')
#else:
#    nights = [night]

#for night in nights:
#    log1 = NightLog.fetch(telescope, night, use_log_cache=False, use_tap_cache=False)
#    log2 = NightLog.fetch(telescope, night, use_log_cache=True)
#
#
#
#
#
#
#
#
