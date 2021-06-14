from ..utils.date import night_to_date_range, add_seconds, date_to_night, \
                         total_seconds, total_hours
from .date import night_to_period

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
from collections import OrderedDict

import numpy as np
import shutil
import os
import json
import re

class NightLog(Log):

    HTML_ROW_GROUPS = OrderedDict(
        ob_start=['ob_start', 'prog_id'],
    )
    HTML_COLUMNS = OrderedDict(
        ob_start=['prog_id', 'nom_prog_id', 'pi', 'instrument', 'object', 
            'exposure', 'ob_start', 'ob_end', 'tel_airm', 'tel_ambi_fwhm',
            'night_hours', 'dark_hours', 'sun_down_hours'],
    )
    HTML_SORT_KEYS = OrderedDict(
        ob_start=None,
    )

    LOG_TYPES = dict(log=['ob_start'])


    @classmethod
    def fetch(cls, telescope, night, *, 
                use_log_cache=True, use_tap_cache=True, 
                rootdir='.', wwwdir='/data/www/twoptwo.com'):
        """Create a new request for a given ESO telescope."""
        
        
        filename = path.filename(telescope=telescope, night=night,
            rootdir=rootdir, log_type='log', ext='csv')
        
        # If file can be read, load and exit

        if use_log_cache and os.path.exists(filename):
        
           try:
               
               log = cls.read(filename, format='ascii.ecsv')
               print(f"{night}: read from cache")
               
               return log 
        
           except Exception as e:
               print(f"{night}: error trying to read from cache {filename}: {e}")

        # Get raw log

        query = NightQuery(telescope=telescope, rootdir=rootdir)
        log = query.fetch(night=night, use_tap_cache=use_tap_cache)
        log.__class__ = cls

        # Add columns with period and night

        log._add_night_info()
      
        # renaming of a few columns

        log['tpl_seqno'].name = 'tpl_no'
        log['tpl_no'].description = 'template number within OB'
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

        log._fill_idle_rows('night', 'astronomical_twilight')

        # fix PIDs

        log._fix_pids()

        # time accounting for night time, dark time, etc.

        log._add_time_accounting()

        # column description

        log._fix_column_description()

        # use human unreadable TABLE_FORMAT == 'ascii.ecsv' to ensure 
        # full reversibility in read/write operations

        log.meta['roodir'] = rootdir
        log.meta['wwwdir'] = wwwdir       
 
        try:
            log.save(format='csv', overwrite=True) 
            print(f"{night}: cached to disk")
        except FileNotFoundError as e:
            print(f"{night}: could not cache to disk: {e}")

        return log

    def _add_ephemeris(self):

        night = self.meta['night'] 
        telescope = self.meta['telescope']
        filename = path.filename(telescope, night=night, 
                    log_type='ephem', ext='json', makedirs=True)

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

    def _create_idle_row(self, i, start, end, name=[], ob_no=-1):

        row0 = np.ndarray((1,), dtype=self.dtype)
        self.insert_row(i)
        row = self[i]

        row['night'] = self.meta['night']
        row['period'] = self.meta['period']
        row['telescope'] = self.meta['telescope']

        for key in 'ob', 'tpl', 'exp':
            row[f"{key}_start"] = start
            row[f"{key}_end"] = end

        uname = [n.upper() for n in name]
        row['pi'] = ' '.join([*name, 'downtime'])[0:20]
        row['prog_id'] =  '/'.join(['IDLE', *uname])[0:14]

        row['ob_name'] = 'Telescope_Idle'
        row['ob_no'] = ob_no

        row['internal'] = False 
        row['slew'] = True

        return row

    def _fill_idle_rows(self, *boundaries):

        self.sort(['internal', 'ob_start', 'tpl_no', 'exp_no'])
        ephem = self.meta['ephemeris']
        
        idle_ob_no = max(self['ob_no']) + 1 if len(self) else 1

        for boundary in boundaries:
            
            if boundary == 'astronomical_twilight':
                name = ['twilight']
            elif boundary == 'night':
                name = ['night']
            else:
                name = []
            
            for tw_start, tw_end in ephem[boundary + '_time']: 

                # on-sky observations are sorted by time
             
                next_ob_start = tw_end
                next_ob_no = -1
           
                # reversed order, so that inserting rows doesn't mess 
                # with the access via index 
           
                in_bounds = ((self['ob_start'] < tw_end) & 
                             (self['ob_end'] > tw_start))
                indices = np.argwhere(~self['internal'] & in_bounds)[:,0]

                for i in reversed(indices):

                    row = self[i]

                    # Within the same OB, no gaps (was taken care of)
                    ob_no = row['ob_no']
                    if ob_no == next_ob_no:
                        continue

                    ob_start, ob_end = row['ob_start','ob_end']

                    # Check if there is a gap
                    if ob_end < next_ob_start:
                        self._create_idle_row(i+1, ob_end, next_ob_start, 
                                   name=name, ob_no=idle_ob_no)
                    idle_ob_no += 1

                    next_ob_no = ob_no
                    next_ob_start = ob_start

                # last index to beginning of night / twilight

                if tw_start < next_ob_start:
                    i0 = indices[0] if len(indices) else 0
                    self._create_idle_row(i0, tw_start, next_ob_start,
                                  name=name, ob_no=idle_ob_no)
                    idle_ob_no += 1

    def _fix_pids(self, programs=None):
        
        pass

    def _fill_missing_technical_obs(self):

        pass

    def _add_time_accounting(self,
            sky_conditions=['night', 'dark', 'astronomical_twilight', 
                            'nautical_twilight', 'civil_twilight', 
                            'sun_down']):

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
            
            col = Column(time, name=sky_time, description=desc, 
                    unit='hour')
            self.add_column(col)

        t = [total_hours(s, e)  for s, e in zip(start, end)]
        time = np.array(t) * accounting
        col = Column(time, name='total_hours', 
            description='number of hours', unit='hour')
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

        ob_no = self['tpl_no'].copy()
        ob_no.name = 'ob_no'
        ob_no.description = 'OB sequence number within the night'
        if len(self):

            new_ob = ((self['ob_name'][1:] != self['ob_name'][:-1]) | 
                      (self['ob_id'][1:] != self['ob_id'][:-1]) |
                      (self['tpl_no'][1:] < self['tpl_no'][:-1]) |
                      (self['tpl_no'][1:] == self['tpl_no'][:-1]) &
                      (self['exp_no'][1:] <= self['exp_no'][:-1]))
       
            new_ob = np.hstack([True, new_ob])
            ob_id = np.cumsum(new_ob) - 1
        
            new_ob_start = self[new_ob]['tpl_start']
            start_rank = 1 + np.argsort(new_ob_start).argsort()

            for id in np.unique(ob_id):
                index = id == ob_id
                ob_no[index] = start_rank[id]
       
        self.add_column(ob_no, index=self.colnames.index('tpl_no'))

    def _add_ob_boundaries(self):
    
        self.sort(['internal', 'ob_no', 'tpl_no', 'exp_no'])
        
        # OB start & end columns
        exec = 'execution of the OB'

        ob_start = self['tpl_start'].copy()
        ob_start.name = 'ob_start'
        ob_start.description = f'estimated start time of the {exec}'
        
        ob_end = self['tpl_end'].copy()
        ob_end.name = 'ob_end'
        ob_end.description = f'estimated end time of the {exec}'

        ob_no = self['ob_no']
        ob_no.description = f'unique OB number within the night'

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
            tracking = ~first_exp['slew']
            start = first_exp['tpl_start']
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
        tpl_end.description = f'estimated end time of {what}'

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
        exp_end.description = 'estimated end time of the exposure'
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
        self['tel_airm'].description = 'reported airmass during the exposure'
        self['tel_ambi_fwhm'].description = 'reported DIMM seeing during the exposure'
        self['tel_ambi_fwhm'].unit = 'arcsec'

    def _add_track_info(self):
        
        typ = self['dp_type']
        sky_types = ['OBJECT', 'STAR', 'OTHER', 'SKY', 'STD', 'FLUX', 
                    'VELOC', 'FOCUS', 'ASTROMETRY','TELLURIC', 'SCIENCE']
        track = np.any([[s in d for d in typ] for s in sky_types], axis=0) 
        
        # Airmass = 1.0 means telescope parked at zenith; real 
        # observations with airmass = 1.000 at both start & end are 
        # pretty rare (there is at best a ~ 54 s window).
        # We do not flag SCIENCE observations for airmass alone
        # though, as it may be a FITS keyword issue.

        tel_airm = self['tel_airm']
        tel_airm[tel_airm.mask] = 1
        track &= (self['dp_cat'] == 'SCIENCE') | (tel_airm > 1.0)
        
        ext_types = ['SCREEN', 'LAMP', *sky_types]
        intern = np.all([[e not in d for d in typ] for e in ext_types], axis=0)
        
        self.add_columns([intern, ~track], names=['internal', 'slew'], 
                indexes=[2,2])
        self['internal'].description = 'flag for internal instrument calibration'
        self['slew'].description = 'flag for non-tracking observations'

    def _add_night_info(self):

        site = self.meta['site']
        location = EarthLocation.of_site(site)
        start = self['tpl_start']
        night = np.array([date_to_night(s, site=location, format='iso') 
                for s in start], dtype='<U10')
        period = np.array([night_to_period(n) for n in night],
                    dtype='<i4')

        self.add_column(night, name='night', index=1)
        self['period'] = period

        self['period'].description = 'ESO observing period'
        self['night'].description = 'observing night'

    def _fix_column_description(self):

        self['telescope'].description = 'telescope name'
        self['instrument'].description = 'instrument name'
        self['prog_id'].description = 'ESO programme ID'
        self['pi'].description = 'name of the principal investigator'
        self['exp_start'].description = 'time at start of exposure'
        self['filter_path'].description = 'list of filtres in the optical path'
        self['object'].description = 'name of the observed object'
        self['target'].description = 'name of the astronomical target'
        self['dp_cat'].description = 'purpose of observation'
        self['dp_tech'].description = 'observing technique'
        self['dp_type'].description = 'type of exposure'
        self['ob_name'].description = 'name of the observing block'
        self['tpl_start'].description = 'time at start of observing template'
        self['exposure'].description = 'cumulated exposure time'
        self['ob_id'].description = 'observing block ID number'
        self['exp_no'].description = 'exposure number within template'

        self['exposure'].unit = 's'
 
        for name in self.colnames:
            if name[-6:] == '_hours':
                self[name].format = '.3f' 
            elif name in ['tel_airm', 'tel_ambi_fwhm']:
                self[name].format = '.2f'
            elif name in ['exposure']:
                self[name].format = '.1f'
