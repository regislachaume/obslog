from ..utils.date import night_to_date_range, add_seconds, date_to_night, \
                         total_seconds, total_hours
from ..utils.ephemeris import night_ephemeris 
from .date import night_to_period
from . import path
from .tapquery import NightQuery
from .log import Log

from pyvo.dal import tap
from astropy.coordinates import EarthLocation
from ..utils.table import Table
from astropy.table import Column
from bs4 import Comment as BSComment

import numpy as np
import shutil
import os
import json
import re

class NightLog(Log):

    TABLE_FORMAT = 'ascii.ecsv'
    
    def publish(self, website='/data/www/twoptwo.com/2.2m/'):

        period = self['period'][0]
        night = self.meta['night']
        rootdir = f'{website}/logs/nightlogs'
        dirname = path.dirname(rootdir, period=period, night=night, 
                         makedirs=True)
        filename = os.path.join(dirname, 'index.shtml')
        shutil.copy2(self.meta['html'], filename) 

    def as_beautiful_soup(self, caption=None, details=['prog_id', 'ob']):
      
        print('NightLog.as_beautiful_soup')
 
        if not isinstance(details, str):
            
            soup = self.as_beautiful_soup(details=details[0])
            
            for detail in details[1:]:
                table = self.as_beautiful_soup(details=detail)
                soup.body.append(table.h2)
                soup.body.append(table.table)

            return soup

        print('Scalar call') 
        night = self.meta['night']

        if details == 'prog_id':

            kept_keys = ['pi', 'prog_id', 'instrument', 'target', 'dark_hours', 
                    'night_hours', 'sun_down_hours']
            group_keys = ['prog_id']
            sort_keys = []
            filter = lambda log: log
            subtitle = "Program summary"
        
        elif details == 'target':

            kept_keys = ['pi', 'prog_id', 'instrument', 'target', 'filter_path',
                       'exposure', 'dark_hours',
                       'night_hours', 'sun_down_hours']
            group_keys = ['prog_id', 'target']
            sort_keys = []
            subtitle = "Compact night log"
            filter = lambda log: log[log['track'] == True]

        elif details == 'ob':

            kept_keys = ['pi', 'prog_id', 'instrument', 'target', 'filter_path',
                      'ob_start', 'ob_end', 'exposure', 'tel_ambi_fwhm',
                      'tel_airm', 'dark_hours',
                      'night_hours', 'sun_down_hours']
            group_keys = ['prog_id', 'target', 'ob_start']
            sort_keys = ['ob_start']
            subtitle = "Detailed night log"
            filter = lambda log: log[log['track'] == True]
        else:
            raise NotImplemented(f'level: {level}')

        summary = filter(self).summary(group_keys)[kept_keys]

        if sort_keys:
            summary.sort(sort_keys)
        
        for key in ['ob_start', 'ob_end']:
            if key in summary.colnames:
                summary[key] = [s[11:16] for s in summary[key]] 
        
        for key in summary.colnames:
            if '_hours' in key:
                summary[key].name = key[:-6]
            elif 'tel_ambi_' in key:
                summary[key].name = key[9:]
            elif 'tel_' in key:
                summary[key].name = key[4:]

        if not caption:
            caption = f"{subtitle} for {night}"

        doc_title = f"Night log for {night}"
        htmldict=dict(
            caption=caption,
            title=doc_title,
            h1=doc_title,
            h2=subtitle,
            table_class='horizontal',
            cssfiles=['../../../../navbar.css', '../../../../twoptwo.css']
        )

        print('calling Table.as_bs')
        soup = Table(summary).as_beautiful_soup(htmldict=htmldict)

        navbar = '#include virtual="../../../../navbar.shtml"'
        soup.body.insert(0, BSComment(navbar))
        
        return soup

    def save_as_html(self, overwrite=False):

        filename = self.meta['html']
        self.write(filename, overwrite=overwrite, format='ascii.html')


    @classmethod
    def fetch(cls, telescope, night, *, 
                use_log_cache=True, use_tap_cache=True, rootdir='.'):
        """Create a new request for a given ESO telescope."""
        
        filename = path.filename(telescope, night=night, name='log',
                        rootdir=rootdir)
        
        # If file can be read, load and exit

        # if use_log_cache and os.path.exists(filename):
        #
        #    try:
        #        
        #        log = cls.read(filename, format=cls.TABLE_FORMAT)
        #        print(f"{night}: read from cache")
        #        
        #        return log 
        #
        #    except Exception as e:
        #        print(f"{night}: error trying to read from cache {filename}: {e}")

        # Get raw log

        query = NightQuery(telescope=telescope, rootdir=rootdir)
        log = query.fetch(night=night, use_tap_cache=use_tap_cache)
        log.__class__ = cls


        # Add columns with period and night

        log._add_night_info()
      
        # renaming of a few columns

        log['tpl_seqno'].name = 'tpl_no'
        log['tpl_expno'].name = 'exp_no'
        log['pi_coi'].name = 'pi'

        print(f"{night}: processing raw log")

        # Read ephemeris
        
        log._add_ephemeris()

        # Average airmass and seeing value = (start + end) / 2 as
        # a quick reference.
        # Note: dalogase may return -1 for missing airmass / seeing (not sure)

        log._average_conditions()

        # Unfortunately, ESO TAP does not give good information about what is
        # internal/on sky and what not.  A reasonable guess here, but not 100%
        # safe, because DPR TYPE is not consistent across ESO instruments. 

        log._add_track_info()
     
        # Guess the end of exposures
        # Once again, the TAP doesn't give readout time/overhead info, that's
        # a wild guess.

        log._add_exp_end()

        #  Add OB number, by start time of first template
        
        log._add_ob_no()

        # Add tpl end

        log._add_tpl_end()

        # Crude start/end times estimated from first and last template.

        log._add_ob_boundaries()
    
        # Avoid overlapping OBs and give some leaway for the inter-OB
        # overheads.  In particular, when the acquisition template is
        # absent, take that into account to fix OB start time.

        log._fix_ob_boundaries()
 
        # Exposure is the important info, det_dit is IR only.  

        log.remove_column('det_dit')

        # Add missing templates such as acquisitions without images

        log._fill_missing_templates()

        # guess missing OBs.  FEROS focus OBs do not leave trace in the
        # exposure dalogase.  Can be inferred from gap in FEROS observations.
        # still not done

        log._fill_missing_technical_obs()

        # report gaps (no exposure reported during night time)
       
        log._fill_idle_rows(boundary='night_time')
        log._fill_idle_rows(boundary='astronomical_twilight_time')

        # fix PIDs

        log._fix_pids()

        # time accounting for night time, dark time, etc.

        log._add_time_accounting()

        # column descriptuon

        log._fix_column_description()

        # use human unreadable TABLE_FORMAT == 'ascii.ecsv' to ensure 
        # full reversibility in read/write operations

        telescope = log['telescope'][0]
        filename = path.filename(telescope, night=night, name='log',
                        rootdir=rootdir)
        htmlfile = path.filename(telescope, 
                        night=night, name='log', ext='shtml',
                        rootdir=rootdir)

        log.meta['fullname'] = filename
        log.meta['html'] = htmlfile
        
        try:
            log.write(filename, format=cls.TABLE_FORMAT, overwrite=True) 
            print(f"{night}: cached to {filename}")
        except FileNotFoundError as e:
            print(f"{night}: could not cache to {filename}")

        return log

    def _add_ephemeris(self):

        night = self.meta['night'] 
        telescope = self['telescope'][0]
        filename = path.filename(telescope, night=night, name='ephemeris', 
                        ext='json', makedirs=True)

        if os.path.exists(filename):

            try:
                with open(filename, 'r') as fh:
                    ephem = json.load(fh)
                    print(f"{night}: ephemeris read from disk")
                    self.meta['ephemeris'] = ephem
                    return ephem
            
            except Exception as e:
                print(f"{night}: error trying to read ephemeris: {e}")
        
        print(f"{night}: compute ephemeris")
        
        ephem = night_ephemeris(self.meta['site'], night)
        
        with open(filename, 'w') as fh:
            json.dump(ephem, fh)

        self.meta['ephemeris'] = ephem
        return ephem

    def _fill_missing_templates(self):

        for i in reversed(range(len(self) - 1)):
                
            this, next = self[i], self[i + 1]
            
            # acquisition
            if next['ob_no'] != this['ob_no'] and next['tpl_no'] > 1:
                acq = np.copy(next)
                acq['tpl_no'] = 1 
                acq['tpl_start'] = acq['ob_start']
                acq['tpl_end'] = next['tpl_start']
                acq['exp_no'] = 1
                acq['exp_start'] = acq['ob_start']
                acq['exp_end'] = next['tpl_start']
                acq['exposure'] = 0
                acq['dp_cat'] = 'ACQUISITION'
                acq['dp_tech'] = 'NONE'
                acq['dp_type'] = 'NONE'
                acq['filter_path'] = '' 
                self.insert_row(i + 1, acq.tolist())

            # other templates
            elif (next['ob_no'] == this['ob_no'] and
                  next['tpl_no'] > this['tpl_no'] + 1):
                tech = np.copy(next)
                tech['tpl_no'] = this['tpl_no'] + 1 
                tech['tpl_start'] = this['tpl_end']
                tech['tpl_end'] = next['tpl_start']
                tech['exp_no'] = 1
                tech['exp_start'] = this['tpl_end']
                tech['exp_end'] = next['tpl_start']
                tech['exposure'] = 0
                tech['dp_cat'] = 'TECHNICAL'
                tech['dp_tech'] = 'NONE'
                tech['dp_type'] = 'NONE'
                tech['filter_path'] = 'NONE' 
                self.insert_row(i + 1, tech.tolist())

    def _create_idle_row(self, i, start, end, name=[]):

        row0 = self[0]

        self.insert_row(i)
        row = self[i]

        for key in 'night', 'period', 'telescope':
            row[key] = row0[key]
        
        for key in 'ob', 'tpl', 'exp':
            row[f"{key}_start"] = start
            row[f"{key}_end"] = end
       
        for key in ['target', 'object', 'instrument', 'dp_cat', 'dp_tech', 
                'dp_type']:
            row[key] = 'IDLE'

        uname = [n.upper() for n in name]
        row['pi'] = ' '.join([*name, 'downtime'])[0:20]
        row['prog_id'] =  '/'.join(['IDLE', *uname])[0:14]

        row['internal'] = False 
        row['track'] = False

        row['ob_name'] = 'Telescope_Idle'

        return row

    def _fill_idle_rows(self, boundary='astronomical_twilight_time'):

        self.sort(['internal', 'ob_start', 'tpl_no', 'exp_no'])
       
        if boundary == 'astronomical_twilight_time':
            name = ['twilight']
        elif boundary == 'night_time':
            name = ['night']
        else:
            name = []
        
 
        ephem = self.meta['ephemeris']
     
        # if there is no astronomical twilight, nothing to report
        if not ephem[boundary]:
            return
        
        tw_start = ephem[boundary][0][0]
        tw_end = ephem[boundary][-1][1]
       
        # on-sky observations are sorted by time
     
        next_ob_start = tw_end
        next_ob_no = -1
       
        # reversed order, so that inserting rows doesn't mess with the 
        # access via index 
       
        in_bounds = (self['ob_start'] < tw_end) & (self['ob_end'] > tw_start)
        indices = np.argwhere(~self['internal'] & in_bounds)[:,0]
        for i in reversed(indices):

            row = self[i]

            # Within the same OB, no gaps (was taken care of)
            ob_no = row['ob_no']
            if ob_no == next_ob_no:
                continue

            # In nautical twilight don't report gaps 
            ob_start, ob_end = row['ob_start','ob_end']

            # Check if there is a gap
            if ob_end < next_ob_start:
                self._create_idle_row(i+1, ob_end, next_ob_start, name=name)

            next_ob_no = ob_no
            next_ob_start = ob_start

        if tw_start < next_ob_start:
            i0 = indices[0] if len(indices) else 0
            self.create_idle_row(i0, tw_start, next_ob_start)

    def _fix_pids(self, programs=None):
        
        pass

    def _fill_missing_technical_obs(self):

        pass

    def _add_time_accounting(self,
            sky_conditions=['night', 'dark', 'astronomical_twilight', 
                            'nautical_twilight', 'civil_twilight', 'sun_down']):

        # ensure to sort by OB, template, and exposure.

        self.sort(['internal', 'ob_start', 'tpl_no', 'exp_no'])

        ephem = self.meta['ephemeris']

        # Given that exposures do not partition a template correctly
        # (e.g. simultaneous detectors), it is impossible to do proper
        # time accounting at the exposure level.  We use the template
        # and give the time to the first exposure of the template.

        start, end = self['tpl_start'], self['tpl_end']
        first_exp = ((self['ob_no'][1:] != self['ob_no'][:-1]) |
                     (self['tpl_no'][1:] != self['tpl_no'][:-1]))
        first_exp = np.hstack([True, first_exp])
        
        # No accounting for internal calibrations will be done.  
        # It's meaningless
        internal = self['internal']

        accounting = first_exp * ~internal 
        
        for sky in sky_conditions:
          
            sky_name = f"{sky}_time"
            sky_time = f"{sky}_hours"
            desc = f"number of hours of {re.sub('_', '', sky)} conditions"
            time = 0.
            
            for ss, se in ephem[sky_name]:
                t = [max(0, total_hours(max(s, ss), min(e, se)))  
                                    for s, e in zip(start, end)]
                time += np.array(t) * accounting 
            
            col = Column(time, name=sky_time, description=desc, unit='hour')
            self.add_column(col)

    def _add_ob_no(self):

        # Several calibrations can run at the same time, so to locate
        # OB boundaries we need to sort first by OB, then by start
        # time.

        self.sort(['instrument', 'tpl_start', 'tpl_no', 'exp_no'])

        # Split into OBs.  Either a change of OB name/ID, or the resetting
        # of the (tpl_seqno, tpl_expno) counters betray a change of OB.
        # Unfortunately, unique OB identification or start time are not
        # contained in the ESO TAP.

        ob_id = np.array([])
        
        if len(self):

            new_ob = ((self['ob_name'][1:] != self['ob_name'][:-1]) | 
                      (self['ob_id'][1:] != self['ob_id'][:-1]) |
                      (self['tpl_no'][1:] < self['tpl_no'][:-1]) |
                      (self['tpl_no'][1:] == self['tpl_no'][:-1]) &
                      (self['exp_no'][1:] <= self['exp_no'][:-1]))
       
            new_ob = np.hstack([True, new_ob])
            ob_id = np.cumsum(new_ob) - 1
        
        ob_no = self['tpl_no'].copy()
        ob_no.name = 'ob_no'
        ob_no.description = 'Observing Block sequence number within the night'
        
        start_rank = 1 + np.argsort(self[new_ob]['tpl_start']).argsort()

        for id in np.unique(ob_id):
            index = id == ob_id
            ob_no[index] = start_rank[id]
       
        self.add_column(ob_no, index=self.colnames.index('tpl_no'))

    def _add_ob_boundaries(self):
    
        self.sort(['internal', 'ob_no', 'tpl_no', 'exp_no'])
        
        # OB start & end columns
        exec = 'execution of the Observing Block'

        ob_start = self['tpl_start'].copy()
        ob_start.name = 'ob_start'
        ob_start.description = f'estimated start time of the {exec}'
        
        ob_end = self['tpl_end'].copy()
        ob_end.name = 'ob_end'
        ob_start.description = f'estimated end time of the {exec}'

        ob_no = self['ob_no']

        for no in np.unique(ob_no):
            index = no == ob_no
            ob_start[index] = self['tpl_start'][index][0] 
            ob_end[index] = self['tpl_end'][index][-1] 

        
        index = self.colnames.index('ob_no') + 1
        self.add_columns([ob_start, ob_end], indexes=[index,index])

    def _fix_ob_boundaries(self):
        
        self.sort(['internal', 'ob_no', 'tpl_start', 'exp_start'])

        ob_id = self['internal', 'ob_no']

        last_end = None
        last_tracking = False
        last_index = None

        for id in np.unique(ob_id):
            
            index = id == ob_id
            
            first_exp = self[index][0]
            tracking, start = first_exp['track','tpl_start']
            tplno, expno = first_exp['tpl_no','exp_no']
            
            end = self['tpl_end'][index][-1]
            

            # Determine the delay between start of OB and start
            # of first template. If acquisition has no image, it won't appear.
            # preset is ~ 4 min, anything from 0 (no preset actually
            # performed) to 6 min (worst case pointing scenario)
            # could happen.
            # We add 2 min in order to avoid reporting loads of mini-gaps.
            if tplno == 2:
                min_delay = 0. # PRESET.NEW = 'F'
                delay = 240. # typical
                max_delay = 480.  # max + 2min
            else:
                min_delay = 0.
                delay = 0.
                max_delay = 120 # 2min leaway

            # Two consecutive on-sky OBs don't overlap.  There should
            # be no gap, so fill with preset as long as it's in the
            # [min_delay, max_delay] range.
            if last_end and tracking and last_tracking:
                
                gap = total_seconds(last_end, start)
                
                if gap > max_delay:
                    overhead = delay
                elif gap < min_delay:
                    overhead = min_delay
                else:
                    overhead = gap

                start = add_seconds(start, -overhead, timespec='seconds')
           
                # if OB are separated by less than minimum delay, the
                # last OB finish time was overestimated.  
                if gap < overhead: 
                    for end_key in 'ob_end', 'exp_end', 'tpl_end':
                        overlap = last_index & (self[end_key] > start)
                        self[end_key][overlap] = start


            # Take mean delay for non-tracking OBs.  It's not important
            # for science time accounting anyway.
            else:
                start = add_seconds(start, -delay, timespec='seconds')
               
            # do the actual OB start / end fix. 
            self['ob_start'][index] = start 
            self['ob_end'][index]  = end
            
            # first template starts with OB.
            is_acq = index & (self['tpl_no'] == 1)
            self['tpl_start'][is_acq] = start

            last_end = end
            last_tracking = tracking
            last_index = index
            

    def _add_tpl_end(self):

        tpl_end = self['tpl_start'].copy()
        tpl_end.name = 'tpl_end'
        what = 'the execution of the observing template'
        tpl_end.description = f'Estimated end time of {what}'

        # in each OB, set the end of templates at the beginning of
        # the next one.  Last template ends at end of last exposure.

        for ob_no in np.unique(self['ob_no']):
            
            index = ob_no == self['ob_no']
            last_begin = None
            
            for tpl_no in reversed(np.unique(self['tpl_no'][index])):

                subindex = index & (tpl_no == self['tpl_no'])
                
                if last_begin:
                    tpl_end[subindex] = last_begin
                else:
                    tpl_end[subindex] = max(self['exp_end'][subindex])
                
                last_begin = self['tpl_start'][subindex][0]

        self.add_column(tpl_end, index=self.colnames.index('tpl_start') + 1)

    def _add_exp_end(self):

        # Mark end of exposure. 

        exp_end = self['exp_start'].copy()
        exp_end.name = 'exp_end'
        exp_end.description = 'Estimated end time of the exposure'
        start, exposure = self['exp_start'], self['exposure']
        
        # IR/optical exposure overheads differ. About 1 min overhead per
        # optical exposure (works pretty well for WFI/FEROS/GROND in the common
        # modes) and 10 s for GROND IR.  Unfortunately the TAP doesn't give the
        # readout mode or time.
        
        overhead = 10 + 50 * self['det_dit'].mask 
        
        # Add time for focus subexposures
        overhead += 320 * (self['dp_tech'] == 'TEL-THROUGH')
        
        exp_end[...] = [add_seconds(s, float(e + o), timespec='seconds') 
                    for s, e, o in zip(start, exposure, overhead)]  

        self.add_column(exp_end)

    def _average_conditions(self):

        for name in ['tel_airm', 'tel_ambi_fwhm']:
            start, end = f"{name}_start", f"{name}_end"
            self[start].mask |= self[start] == -1
            self[end].mask |= self[end] == -1
            self[start] = (self[start].data + self[end].data) / 2 
            self[start].name = name
            self.remove_column(end)
        self['tel_airm'].description = 'Estimated airmass during the exposure'
        self['tel_ambi_fwhm'].description = 'Estimated DIMM seeing during the exposure'
        self['tel_ambi_fwhm'].unit = 'arcsec'

    def _add_track_info(self):
        
        typ = self['dp_type']
        sky_types = ['OBJECT', 'STAR', 'OTHER', 'SKY', 'STD', 'FLUX', 'VELOC', 
                        'FOCUS', 'ASTROMETRY','TELLURIC', 'SCIENCE']
        track = np.any([[s in d for d in typ] for s in sky_types], axis=0) 
        
        # Airmass = 1.0 means telescope parked at zenith; real 
        # observations with airmass = 1.000 at both start & end are 
        # pretty rare (there is at best a ~ 54 s window).
        tel_airm = self['tel_airm']
        tel_airm[tel_airm.mask] = 1
        track &= (self['dp_cat'] == 'SCIENCE') | (tel_airm > 1.0)
        
        ext_types = ['SCREEN', 'LAMP', *sky_types]
        intern = np.all([[e not in d for d in typ] for e in ext_types], axis=0)
        
        self.add_columns([intern, track], names=['internal', 'track'], indexes=[2,2])
        self['internal'].description = 'Flag for internal instrument calibration'
        self['track'].description = 'Flag for on-sky observations (tracking)'

    def _add_night_info(self):

        site = self.meta['site']
        location = EarthLocation.of_site(site)
        start = self['tpl_start']
        night = np.array([date_to_night(s, site=location) for s in start])
        period = np.array([night_to_period(n) for n in night])

        self.add_column(night, name='night', index=1)
        self['period'] = period

        self['period'].description = 'ESO observing period'
        self['night'].description = 'Observing night'

    def _fix_column_description(self):

        self['telescope'].description = 'Telescope name'
        self['instrument'].description = 'Instrument name'
        self['prog_id'].description = 'ESO programme ID'
        self['pi'].description = 'Name of the principal investigator'
        self['exp_start'].description = 'Time at start of exposure'
        self['filter_path'].description = 'List of filtres'
        self['object'].description = 'Name of the observation or target'
        self['target'].description = 'Name of the astronomical target'
        self['dp_cat'].description = 'Purpose of observation'
        self['dp_tech'].description = 'Observing technique'
        self['dp_type'].description = 'Type of exposure'
        self['ob_name'].description = 'Name of the observing block'
        self['tpl_start'].description = 'Time at start of observing template'

        for name in self.colnames:
            if name[-6:] == '_hours':
                self[name].format = '.3f' 
            elif name in ['tel_airm', 'tel_ambi_fwhm']:
                self[name].format = '.2f'
            elif name in ['exposure']:
                self[name].format = '.1f'
