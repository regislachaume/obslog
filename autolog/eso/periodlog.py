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
        night=['night', 'slew', 'instrument'],
        object=['internal', 'slew', 'instrument', 'prog_id', 'object'],
    )
    HTML_COLUMNS = OrderedDict(
        night=['night', 'instrument', 'prog_id', 
               'night_hours', 'dark_hours', 'sun_down_hours'],
        object=['object', 'instrument', 'prog_id', 'night', 
                    'n_ob', 'n_exp',  'exposure'],
    )
    HTML_SORT_KEYS = OrderedDict(
        night=['night'],
        object=['internal', 'slew', 'instrument', 'prog_id'],
    )

    def publish(self, website='/data/www/twoptwo.com/'):

        period = self['period'][0]
        telescope = self.meta['telescope']

        rootdir = f'{website}/{telescope}/logs' 
        dirname = path.dirname(rootdir, period=period, makedirs=True)
        filename = os.path.join(dirname, 'index.shtml')
        shutil.copy2(self.meta['html_filename'], filename) 

    @classmethod
    def fetch(cls, telescope, period, *, 
                use_log_cache=True, use_tap_cache=True, rootdir='.'):
        """Create a new request for a given ESO telescope."""
        
        filename = path.filename(telescope, period=period, name='log',
                        rootdir=rootdir)
               
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
            del log.meta['html_filename']
            del log.meta['csv_filename']

        log.meta['ephemeris'] = ephem

        log = cls(table.vstack(logs))
        for name in log.colnames:
            log[name].description = logs[0][name].description
            log[name].format = logs[0][name].format
            log[name].unit = logs[0][name].unit

        csv_filename = path.filename(telescope, period=period, 
                            name='log', rootdir=rootdir)
        html_filename = path.filename(telescope, period=period, 
                            name='log', ext='shtml', rootdir=rootdir)

        log.meta['csv_filename'] = csv_filename
        log.meta['html_filename'] = html_filename
 

        try:
            log.save(format='csv', overwrite=True)
            print(f"period {period}: cached to {csv_filename}")
        except FileNotFoundError as e:
            print(f"period {period}: could not cache to {html_filename}")

        return log
