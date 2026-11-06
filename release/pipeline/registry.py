"""Registry of the 11 Volve wellbores that have an effective-porosity (PHIF) log
and a usable deviation survey. Key = NPD wellbore id (as in the LAS WELL header),
except F-11 T2, whose LAS header carries the name instead of an NPD id."""

WELL_NAMES = {
    'NPD-3145': '15/9-19 A', 'NPD-7405': '15/9-F-1C', 'NPD-7079': '15/9-F-11A',
    'NPD-7080': '15/9-F-11B', 'NPD-5599': '15/9-F-12', 'NPD-2105': '15/9-19 SR',
    'NPD-7223': '15/9-F-1', 'NPD-7224': '15/9-F-1A', 'NPD-7264': '15/9-F-1B',
    'NPD-7289': '15/9-F-15D', 'F-11T2': '15/9-F-11T2',
}
WELL_ORDER = ['NPD-3145', 'NPD-7405', 'NPD-7079', 'NPD-7080', 'NPD-5599',
              'NPD-2105', 'NPD-7223', 'NPD-7224', 'NPD-7264', 'NPD-7289', 'F-11T2']
