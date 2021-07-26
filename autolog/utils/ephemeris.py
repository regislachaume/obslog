from ..utils.date import night_to_date_range, add_seconds, total_seconds
from ..utils.telescope import parse_telescope
from ..eso import path

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.time import Time
from astropy.table import Table, Column
from astroplan import Observer, AstroplanWarning
from astropy.units import deg, hPa
import warnings
import re

import numpy as np
import os
import json

def _down_span(observer, start, midnight, end, type='night'):

    w = warnings.catch_warnings() 
    warnings.simplefilter('error', category=AstroplanWarning)

    if type == 'down':
        h = -0.8333 * deg
    elif type == 'nautical':
        h = -6 * deg
    elif type == 'astronomical':
        h = -12 * deg
    elif type == 'night':
        h = -18 * deg
    else:
        raise TypeError('bad sun down type')

    is_down = observer.is_night(midnight, horizon=h)

    if not is_down:
        return []

    # if rise and set do not happen on the same day, astroplan 
    # yields warning (thrown as exception). 
    try:
        set = observer.sun_set_time(midnight, 'previous', horizon=h)
    except AstroplanWarning:
        set = start

    try:
        rise = observer.sun_rise_time(midnight, 'next', horizon=h)
    except AstroplanWarning:
        rise = end

    return [max(start, set).isot, min(end, rise).isot]

def _get_dark(obs, night_time):

    w = warnings.catch_warnings() 
    warnings.simplefilter('error', category=AstroplanWarning)


    if not night_time:
        return dict(dark_time=[], dark_hours=0.)

    epsilon = 1/86400
    night_start = Time(night_time[0][0])
    night_end = Time(night_time[0][1])
    h = -0.8333 * deg
    t = Time(night_start)
    
    dark_time = []
   
    while t < night_end:

        alt = obs.moon_altaz(t + epsilon).alt 
        is_dark = alt <= h
        
        if is_dark:

            try:
                moon_rise = obs.moon_rise_time(t, 'next', horizon=h)
                moon_rise = min(night_end, moon_rise)
            except AstroplanWarning as e:
                moon_rise = night_end

            dark_time.append((t.isot, moon_rise.isot[0:19]))
            t = moon_rise

        try:
            t = obs.moon_set_time(t, 'next', horizon=h) 
            t = min(night_end, t)
        except AstroplanWarning as e:
            t = night_end

    dark_hours = sum(total_seconds(*d) for d in dark_time) / 3600

    return dict(dark_time=dark_time, dark_hours=dark_hours)

def _get_twilights(observer, start, midnight, end):

    down = _down_span(observer, start, midnight, end, type='down')
    naut = _down_span(observer, start, midnight, end, type='nautical')
    astron = _down_span(observer, start, midnight, end, type='astronomical')
    night = _down_span(observer, start, midnight, end, type='night')

    if down:
        sun_down_time = [down]
        if naut:
            civil_twilight_time = [[down[0], naut[0]], [naut[1], down[1]]]
            if astron:
                nautical_twilight_time = [[naut[0], astron[0]],
                                          [astron[1], naut[1]]]
                if night:
                    twilight_time = [[astron[0], night[0]],
                                     [night[1], astron[1]]]
                    night_time = [night]
                else:
                    twilight_time = [astron]
                    night_time = []
            else:
                nautical_twilight_time = [naut]
                twilight_time = []
        else:
            civil_twilight_time = [down]
            nautical_twilight_time = []
    else:
        sun_down_time = []

    sun_down_hours = sum(total_seconds(*d) 
                        for d in sun_down_time) / 3600
    night_hours = sum(total_seconds(*d) 
                        for d in night_time) / 3600
    twilight_hours = sum(total_seconds(*d) 
                        for d in twilight_time) / 3600
    nautical_twilight_hours = sum(total_seconds(*d) 
                        for d in nautical_twilight_time) / 3600
    civil_twilight_hours = sum(total_seconds(*d) 
                        for d in civil_twilight_time) / 3600


    twilights = dict(
                    sun_down_time = sun_down_time,
                    sun_down_hours = sun_down_hours,
                    civil_twilight_time = civil_twilight_time,
                    civil_twilight_hours = civil_twilight_hours,
                    nautical_twilight_time = nautical_twilight_time,
                    nautical_twilight_hours = nautical_twilight_hours,
                    twilight_time = twilight_time,
                    twilight_hours = twilight_hours,
                    night_time = night_time,
                    night_hours = night_hours,
                )
    
    return twilights
                    
def night_ephemeris(location, night, /, *, basedir='.', overwrite=False):

    if isinstance(location, str):

        try:
            location, telescope_names = parse_telescope(location)
            telescope = telescope_names[0]
        except NotImplementedError:
            telescope = None

        location = EarthLocation.of_site(location)

    elif isinstance(location, tuple):
        location = EarthLocatation(*location)
    
    # try to read from file

    if telescope is not None:

        filename = path.filename(telescope, night=night,
                    log_type='ephem', ext='json', makedirs=True)
        try:
            with open(filename, 'r') as fh:
                ephem = json.load(fh)
                print(f"{night}: ephemeris read from disk")
                return ephem

        except Exception as e:
            pass
            
    print(f"{night}: compute ephemeris")

    try: # locally redefines Time.precision

        Time.precision = 0
        
        start, end = night_to_date_range(night, site=location)
        start, end = Time(start), Time(end)
        observer = Observer(location, pressure=0 * u.hPa)
        midnight = observer.midnight(start, 'next')

        twilights = _get_twilights(observer, start, midnight, end)
        dark = _get_dark(observer, twilights['night_time'])
        moon_illumination = observer.moon_illumination(midnight)

        del Time.precision
        
        ephem = dict(moon_illumination=moon_illumination, **dark, **twilights)

    except Exception as e:

        del Time.precision
        raise e

    # save to telescope ephemeris 

    if telescope is not None:
        
        with open(filename, 'w') as fh:
            json.dump(ephem, fh)
        
    return ephem

