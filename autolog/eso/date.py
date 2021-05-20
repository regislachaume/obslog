from datetime import date, timedelta
from ..utils.date import tonight

DAY = timedelta(days=1)

def night_to_period(night):
    if isinstance(night, str):
        night = date.fromisoformat(night)
    period = (night.year - 1968) * 2 + (night.month + 2) // 6
    return period

def period_start(period, *, format='date'):
    year = (period - 1) // 2 + 1968
    month = 4 + 6 * ((period - 1) % 2)
    night = date(year, month, 1)
    if format == 'iso':
        night = night.isoformat()
    return night

def period_end(period, *, format='date'):
    return period_start(period + 1, format=format)

def period_nights(period, *, format='date'):
    start = period_start(period)
    end = period_end(period)
    night = start
    end = min(end, tonight())
    while night < end: 
        yield night.isoformat() if format == 'iso' else night
        night += DAY 
    
