from .date import night_to_period 
import os


def _get_path(telescope, /, *, rootdir='.', period=None, night=None):

    if night and not period:
        period = night_to_period(night)

    path = [rootdir, telescope]
    if period:
        path.append(f"P{period}")
    if night:
        path.append(night)

    return path
    
def _get_name(telescope, /, *, rootdir='.',
            period=None, night=None, name=None, ext=None, makedirs=False):

    path = _get_path(telescope, rootdir=rootdir, period=period, night=night)
    dir = os.path.join(*path)

    if makedirs:
        os.makedirs(dir, exist_ok=True)

    if name is None:
        return dir

    name = f"{'-'.join(path[1:])}-{name}.{ext}"
    name = os.path.join(dir, name)

    return name 

def dirname(telescope, /, *, rootdir='.',
        period=None, night=None, makedirs=False):

    return _get_name(telescope, rootdir=rootdir, makedirs=makedirs,
                period=period, night=night)

def filename(telescope, /, *, rootdir='.', name, ext='dat',
        period=None, night=None, makedirs=False):

    return _get_name(telescope, rootdir=rootdir, makedirs=makedirs,
            period=period, night=night, name=name, ext=ext)

