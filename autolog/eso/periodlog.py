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
        night=['night', 'slew', 'instrument', 'prog_id'],
        object=['internal', 'slew', 'instrument', 'prog_id', 'object'],
        dp_cat=['internal', 'slew', 'instrument', 'dp_cat'],
        prog_id=['internal', 'slew', 'tac', 'prog_id'],
    )
    HTML_COLUMNS = OrderedDict(
        night=['night', 'instrument', 'prog_id', 'dp_cat', 'pi', 
               'night_hours', 'dark_hours', 'sun_down_hours'],
        object=['instrument', 'prog_id', 'object', 'night', 
                    'n_ob', 'n_exp',  'exposure'],
        dp_cat=['instrument', 'dp_cat', 
               'night_hours', 'dark_hours', 'sun_down_hours'],
        prog_id=['tac', 'prog_id',  'night_hours', 'dark_hours', 
                'sun_down_hours'],
    )
    HTML_SORT_KEYS = OrderedDict(
        night=['night'],
        object=['internal', 'slew', 'instrument', 'prog_id'],
        dp_cat=['instrument'],
        prog_id=['tac', 'prog_id'],
    )

    LOG_TYPES = dict(log=['night'], target=['object'],
                    report=['dp_cat', 'prog_id'])

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
            log.save(format='html')
            log.publish()
        
        # append ephemeris 
        ephem = {}
        for key in logs[0].meta['ephemeris']:
            values = [l.meta['ephemeris'][key] for l in logs]
            if '_hours' in key:
                ephem[key] = sum(values)
            elif '_time' in key:
                ephem[key] = np.vstack([v for v in values if v])
       
        for log in logs:
            del log.meta['night']
            del log.meta['ephemeris']

        log.meta['ephemeris'] = ephem

        log = cls(table.vstack(logs))
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
