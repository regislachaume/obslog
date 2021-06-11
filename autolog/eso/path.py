from .date import night_to_period 
import os


def _get_path(telescope, /, *, log_type='log',
                    rootdir='.', period=None, night=None):

    if night and not period:
        period = night_to_period(night)

    path = [rootdir, telescope, f"{log_type}s"]
    if period:
        path.append(f"P{period:03}")
    if night:
        path.append(night)

    return path
    
def _get_name(telescope, /, *, rootdir='.', log_type='log',
            period=None, night=None, name=None, ext=None, makedirs=False,
            is_dir, **unused):

    path = _get_path(telescope, log_type=log_type,
            rootdir=rootdir, period=period, night=night)
    dir = os.path.join(*path)

    if makedirs:
        os.makedirs(dir, exist_ok=True)

    if is_dir:
        return dir

    if ext in ['html', 'shtml']:
        name = f"index.{ext}"
    else:
        elem = [log_type, path[1], *path[3:]]
        name = f"{'-'.join(elem)}.{ext}"
    name = os.path.join(dir, name)

    return name 

def dirname(telescope, rootdir='.', log_type='log',
        period=None, night=None, makedirs=False,):

    return _get_name(telescope, rootdir=rootdir, log_type=log_type,
                makedirs=makedirs,
                period=period, night=night, is_dir=True)

def filename(telescope, rootdir='.', log_type='log', ext='csv',
        period=None, night=None, makedirs=False):

    return _get_name(telescope, rootdir=rootdir, log_type=log_type,
            makedirs=makedirs,
            period=period, night=night, ext=ext, is_dir=False)

