_ls = 'La Silla Observatory'
_par = 'Paranal Observatory'

TELESCOPES = {
    ('ESO-2.2m', 'ESO/2.2m', '2.2m', 'MPI-2.2', 'MPG-2.2', 
     'MPG/ESO-2.2', 'MPG/ESO-220'): _ls,
    ('ESO-NTT', 'ESO/NTT', 'NTT', 'ESO-NTT', 'VLT-NONE'): _ls,
    ('ESO-3.6m', 'ESO/3.6m', '3.6m', 'ESO-3P6'): _ls,
    ('ESO-UT1', 'ESO/UT1', 'UT1'): _par,
    ('ESO-UT2', 'ESO/UT2', 'UT2'): _par,
    ('ESO-UT3', 'ESO/UT3', 'UT3'): _par,
    ('ESO-UT4', 'ESO/UT4', 'UT4'): _par,
    ('ESO-VLTI', 'ESO/VLTI', 'VLTI'): _par,
    ('ESO-VISTA', 'ESO/VISTA', 'VISTA'): _par,
    ('ESO-VST', 'ESO/VST', 'VST'): _par,
}

def parse_telescope(telescope):


    for telescope_names, site in TELESCOPES.items():
        if telescope in telescope_names:
            return site, telescope_names

    raise NotImplementedError(f'telescope {telescope} not recognised')
