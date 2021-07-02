from ..utils.date import tonight
from .date import period_nights
from . import path
from .log import Log
from .nightlog import NightLog

from astropy import table
from collections import OrderedDict
import shutil
import os
import numpy as np

class PeriodLog(Log):

    HTML_ROW_GROUPS = OrderedDict(
        night=['night', 'slew', 'instrument', 'pid'],
        object=['internal', 'slew', 'instrument', 'pid', 'object'],
        dp_cat=['internal', 'slew', 'dp_cat', 'instrument'],
        pid=['internal', 'slew', 'tac', 'pid'],
    )
    HTML_COLUMNS = OrderedDict(
        night=['night', 'instrument', 'pid', 'dp_cat', 'pi', 
               'night_hours', 'dark_hours', 'sun_down_hours'],
        object=['instrument', 'pid', 'object', 'night', 
                    'n_ob', 'n_exp',  'exposure'],
        dp_cat=['dp_cat', 'instrument', 
               'night_hours', 'dark_hours', 'sun_down_hours'],
        pid=['tac', 'pid',  'instrument', 'pi', 'night_hours', 'dark_hours', 
                'twilight_hours', 'sun_down_hours'],
    )
    HTML_SORT_KEYS = OrderedDict(
        night=['night','slew'],
        object=['internal', 'slew', 'instrument', 'pid'],
        dp_cat=['dp_cat'],
        pid=['tac'],
    )
    HTML_PROGRESS = OrderedDict(
        dp_cat='time',
        pid='allocation',
    )
    LOG_TYPES = dict(log=['night'], target=['object'],
                    report=['dp_cat', 'pid'])

    @classmethod
    def fetch(cls, telescope, period, *, 
                use_log_cache=True, use_tap_cache=True, rootdir='.'):
        """Create a new request for a given ESO telescope."""
        
        filename = path.filename(telescope, period=period, log_type='log',
                        rootdir=rootdir, ext='csv')
               
        today =  tonight(format='iso')
        opts = dict(rootdir=rootdir, use_log_cache=use_log_cache, 
                                    use_tap_cache=use_tap_cache)

        logs = [NightLog.fetch(telescope, night, **opts)
            for night in period_nights(period, format='iso') if night < today]

        for log in logs:
            log.fix_pids()

        # append ephemeris 
        ephem = {}
        for key in logs[0].meta['ephemeris']:
            values = [l.meta['ephemeris'][key] for l in logs]
            if '_hours' in key:
                ephem[key] = sum(values)
            elif '_time' in key:
                ephem[key] = np.vstack([v for v in values if v])
       

        log = cls(table.vstack(logs, metadata_conflicts='silent'))
        
        del log.meta['night']
        log.nightlogs = logs
        log.meta['ephemeris'] = ephem

        for name in log.colnames:
            log[name].description = logs[0][name].description
            log[name].format = logs[0][name].format
            log[name].unit = logs[0][name].unit

        try:
            log.save(format='csv', overwrite=True)
            print(f"period {period}: cached to disk")
        except FileNotFoundError as e:
            print(f"period {period}: could not cache to dist: {e}")

        return log

    def save(self, *, log_type='log', overwrite=True, format='csv'):

        super().save(log_type=log_type, overwrite=overwrite, format=format)

        for log in self.nightlogs:
            if log_type not in log.LOG_TYPES:
                break
            log.save(log_type=log_type, overwrite=overwrite, format=format)
    
    def publish(self, log_type='log'):

        super().publish(log_type=log_type)

        for log in self.nightlogs:
            if log_type not in log.LOG_TYPES:
                break
            log.publish(log_type=log_type)
