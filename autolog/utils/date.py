from datetime import datetime as DateTime, \
                     date as Date, \
                     timedelta as TimeDelta

DAY = TimeDelta(days=1)

def date_to_night(date, *, site=None, format='date'):
    if isinstance(date, str):
        date = DateTime.fromisoformat(date)
    lon = site.lon.hour if site is not None else 0.
    date -= TimeDelta(hours=12 - lon)
    night = date.date()
    if format == 'iso':
        night = night.isoformat()
    return night

def night_to_midnight(night, *, site=None, format='date'):
    if isinstance(night, str):
        night = DateTime.fromisoformat(night)
    lon = site.lon.hour if site is not None else 0.
    midnight = night + TimeDelta(hours=24 - lon)
    if format == 'iso':
        midnight = midnight.isoformat(timespec='seconds')
    return midnight

def night_to_date_range(night, *, site=None, format='date'):
    if isinstance(night, str):
        night = DateTime.fromisoformat(night)
    lon = site.lon.hour if site is not None else 0.
    start = night + TimeDelta(hours=12 - lon)
    end = start + DAY
    if format == 'iso':
        start = start.isoformat(timespec='seconds')
        end = end.isoformat(timespec='seconds')
    return start, end
    

def tonight(*, site=None, format='date'):
    date = DateTime.now()
    return date_to_night(date, site=site, format=format)

def total_seconds(d1, d2):
    dt = DateTime.fromisoformat(d2) - DateTime.fromisoformat(d1)
    return dt.total_seconds()

def total_hours(d1, d2):
    return total_seconds(d1, d2) / 3600

def add_seconds(date, dt, timespec='milliseconds'):
    if isinstance(date, str):
        d = DateTime.fromisoformat(date)
    else:
        d = date
    d += TimeDelta(seconds=dt)
    if isinstance(date, str):
        d = d.isoformat(timespec=timespec)
    return d

