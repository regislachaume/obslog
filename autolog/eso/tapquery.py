from ..utils.date import night_to_date_range
from .date import night_to_period

from . import path

from pyvo.dal import tap
from astropy.coordinates import EarthLocation
from astropy.table import Table
from collections import OrderedDict

import numpy as np
import os
        
class NightQuery:
    """ESO TAP query for raw archive data. 

It keeps a local copy of requests to save on internet bandpass"""

    URL = 'http://archive.eso.org/tap_obs'
    TABLE = 'dbo.raw'
    KEYS = {'period': '<i2',
            'object': '<U32', 
            'target': '<U32', 
            'ra': '<f8', 
            'dec': '<f8', 
            'telescope': '<U20', 
            'instrument': '<U8', 
            'prog_id': '<U14', 
            'pi_coi': '<U20',
            'dp_cat': '<U11', 
            'dp_tech': '<U32', 
            'dp_type': '<U32', 
            'exposure': '<f4', 
            'det_dit': '<f4', 
            'filter_path': '<U32', 
            'ob_name': '<U64', 
            'ob_id': '<i4',
            'tel_airm_start': '<f4', 
            'tel_airm_end': '<f4', 
            'tel_ambi_fwhm_start': '<f4', 
            'tel_ambi_fwhm_end': '<f4',
            'tpl_seqno': '<i4', 
            'tpl_start': '<U19', 
            'tpl_expno': '<i4', 
            'exp_start': '<U19',
           }
    TABLE_FORMAT = 'ascii.ecsv'
        
    def __init__(self, *, telescope, rootdir='.'):
        """Create a new request for a given ESO telescope."""
 
        # La Silla telescopes were poorly handled in headers

        eso_2p2 = ('ESO-2.2m', 'ESO/2.2m', '2.2m', 'MPI-2.2', 'MPG-2.2', 'MPG/ESO-2.2', 'MPG/ESO-220')
        eso_ntt = ('ESO-NTT', 'ESO/NTT', 'NTT', 'ESO-NTT', 'VLT-NONE')
        eso_3p6 = ('ESO-3.6m', 'ESO/3.6m', '3.6m', 'ESO-3P6',)

        if telescope in eso_2p2:
            telescope_names = eso_2p2
            site = 'La Silla Observatory'
        elif telescope in eso_ntt:
            telescope_names = eso_ntt
            site = 'La Silla Observatory'
        elif telescope in eso_3p6:
            telescope_names = eso_3p6
            site = 'La Silla Observatory'
        else:
            telescope_names = (telescope,)
            site = 'Paranal Observatory'

        # Set the TAP & defaults

        self.tap = tap.TAPService(self.URL)
        self.site = site
        self.location = EarthLocation.of_site(site)
        self.telescope_names = telescope_names
        self.rootdir = rootdir

    def fetch(self, *, night, use_tap_cache=False):
        """Query the list of frames from ESO TAP service for a given night."""

        telescope = self.telescope_names[0]
        filename = path.filename(telescope, night=night, name='tap',
                        rootdir=self.rootdir, makedirs=True)

        # If file can be read, load and exit
        
        if use_tap_cache and os.path.exists(filename):

            # try:
                cls = type(self)
                tab = Table.read(filename, format=self.TABLE_FORMAT)
                cls._fix_column_types(tab)
                print(f"{night}: raw log read from disk")
                return tab

            #except Exception as e:
            #    print(f"{night}: error trying to read raw log: {e}")

        # Retrive from ESO using SQL-like language query for Table-access
        # protocol

        print(f"{night}: fetching raw log from ESO TAP service")

        loc = self.location
        start, end = night_to_date_range(night, site=loc, format='iso')

        query = f"""
            SELECT {', '.join(self.KEYS.keys())}
            FROM {self.TABLE}
            WHERE 
                    exp_start BETWEEN '{start}' AND '{end}'
                AND telescope in {self.telescope_names}
            ORDER BY exp_start ASC
        """

        result = self.tap.search(query=query)
        tab = result.to_table()

        # Add some meta information

        period = night_to_period(night)
        tab.meta = OrderedDict(fullname=filename, night=night, site=self.site,
            lon=loc.lon.to_value('deg'), lat=loc.lat.to_value('deg'), 
            alt=loc.height.si.value)
        
        # char of variable size return by ESO TAP is rendered as object
        # by pyvo.  We fix that to get strings.  Empty ones are considered
        # masked.

        self._fix_column_types(tab)

        # Fix telescope name to ensure it's consistent over instruments
        # and nights.

        self._fix_telescope(tab)
    
        # use human unreadable TABLE_FORMAT == 'ascii.ecsv' to ensure 
        # full reversibility in read/write operations

        try:
            tab.write(filename, format=self.TABLE_FORMAT, overwrite=True) 
            print(f"Cached to {filename}")
        except FileNotFoundError as e:
            print(f"Could not cache to {filename}")

        return tab
    
    @classmethod
    def _fix_column_types(cls, tab):
        
        for i, name in enumerate(tab.colnames):
        
            col = tab[name]
 
            if col.dtype.char in 'OU':
                
                str_ = cls.KEYS.get(name, '<U0')
                dtype = np.dtype(str_)
               
                if (len := dtype.itemsize // dtype.alignment):
                    new_col = [c[0:len] if c else c for c in col]
                else:
                    new_col = [c for c in col]
            
                new_col = np.ma.masked_array(new_col, dtype=dtype)
                new_col.mask |= col == '' 
                tab.remove_column(name) 
                tab.add_column(new_col, name=name, index=i)
            
            elif (str_ := cls.KEYS.get(name, '')) and col.dtype.str != str_:
            
                dtype = np.dtype(str_)
                new_col = np.ma.masked_array(col, dtype=dtype, mask=col.mask)
                tab.remove_column(name) 
                tab.add_column(new_col, name=name, index=i)

            if col.dtype.char in 'if' and hasattr(col, 'mask'):

                col[col.mask] = np.ma.masked_array(0., mask=True)  
    
    def _fix_telescope(self, tab):

        tab['telescope'] = self.telescope_names[0]

