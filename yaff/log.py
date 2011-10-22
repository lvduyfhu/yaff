# YAFF is yet another force-field code
# Copyright (C) 2008 - 2011 Toon Verstraelen <Toon.Verstraelen@UGent.be>, Center
# for Molecular Modeling (CMM), Ghent University, Ghent, Belgium; all rights
# reserved unless otherwise stated.
#
# This file is part of YAFF.
#
# YAFF is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# YAFF is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
# --


import sys, atexit, os, datetime, getpass
from contextlib import contextmanager

from molmod.units import kjmol, kcalmol, electronvolt, angstrom, nanometer, \
    femtosecond, picosecond, amu, deg, gram, centimeter
from yaff.timer import timer


__all__ = ['ScreenLog', 'log']


head_banner = r"""
_____/\\\________/\\\___/\\\\\\\\\______/\\\\\\\\\\\\\\\__/\\\\\\\\\\\\\\\______
_____\///\\\____/\\\/__/\\\\\\\\\\\\\___\ \\\///////////__\ \\\///////////______
________\///\\\/\\\/___/\\\/////////\\\__\ \\\_____________\ \\\________________
___________\///\\\/____\ \\\_______\ \\\__\ \\\\\\\\\\\_____\ \\\\\\\\\\\_______
______________\ \\\_____\ \\\\\\\\\\\\\\\__\ \\\///////______\ \\\///////_______
_______________\ \\\_____\ \\\/////////\\\__\ \\\_____________\ \\\_____________
________________\ \\\_____\ \\\_______\ \\\__\ \\\_____________\ \\\____________
_________________\ \\\_____\ \\\_______\ \\\__\ \\\_____________\ \\\___________
__________________\///______\///________\///___\///______________\///___________


                 Welcome to YAFF - yet another force field code

                                   Written by
                  Toon Verstraelen(1)* and Louis Vanduyfhuys(1)

(1) Center for Molecular Modeling, Ghent University Belgium.
* mailto: Toon.Vesrtraelen@UGent.be

In a not-too-distant future, this program will be renamed to NJAFF, which stands
for 'not just another force field code'. Please, bear with us.
"""


foot_banner = r"""
__/\\\__________________________________________________________________/\\\____
  \ \\\                                                                 \ \\\
   \ \\\      End of file. Thanks for using YAFF! Come back soon!!       \ \\\
____\///__________________________________________________________________\///__
"""


class Unit(object):
    def __init__(self, kind, conversion, notation, format):
        self.kind = kind
        self.conversion = conversion
        self.notation = notation
        self.format = format

    def __call__(self, value):
        return self.format % (value/self.conversion)


class UnitSystem(object):
    def __init__(self, *units):
        self.units = units
        # check for duplicates
        for i0, unit0 in enumerate(self.units):
            for unit1 in self.units[:i0]:
                if unit0.kind == unit1.kind:
                    raise ValueError('The unit of \'%s\' is encountered twice.' % unit0.kind)

    def log_info(self):
        if log.do_low:
            with log.section('UNITS'):
                log('The following units will be used below:')
                log.hline()
                log('Kind          Conversion               Format Notation')
                log.hline()
                for unit in self.units:
                    log('%13s %21.15e %9s %s' % (unit.kind, unit.conversion, unit.format, unit.notation))
                log.hline()
                log('The internal data is divided by the corresponding conversion factor before it gets printed on screen.')

    def apply(self, some):
        for unit in self.units:
            some.__dict__[unit.kind] = unit


class ScreenLog(object):
    # log levels
    silent = 0
    warning = 1
    low = 2
    medium = 3
    high = 4
    debug = 5

    # screen parameters
    margin = 8
    width = 72

    # unit systems
    # TODO: the formats may need some tuning
    joule = UnitSystem(
        Unit('energy', kjmol, 'kJ/mol', '%10.1f'),
        Unit('temperature', 1, 'K', '%10.1f'),
        Unit('length', angstrom, 'A', '%10.4f'),
        Unit('invlength', 1/angstrom, 'A^-1', '%10.5f'),
        Unit('area', angstrom**2, 'A^2', '%10.3f'),
        Unit('volume', angstrom**3, 'A^3', '%10.3f'),
        Unit('time', femtosecond, 'fs', '%10.1f'),
        Unit('mass', amu, 'amu', '%10.5f'),
        Unit('charge', 1, 'e', '%10.5f'),
        Unit('force', kjmol/angstrom, 'kJ/mol/A', '%10.1f'),
        Unit('forceconst', kjmol/angstrom**2, 'kJ/mol/A**2', '%10.1f'),
        Unit('velocity', angstrom/femtosecond, 'A/fs', '%10.5f'),
        Unit('acceleration', angstrom/femtosecond**2, 'A/fs**2', '%10.5f'),
        Unit('angle', deg, 'deg', '%10.5f'),
        Unit('c6', 1, 'E_h*a_0**6', '%10.5f'),
        Unit('diffconst', angstrom**2/picosecond, 'A**2/ps', '%10.5f'),
        Unit('density', gram/centimeter**3, 'g/cm^3', '%10.3f'),
    )
    cal = UnitSystem(
        Unit('energy', kcalmol, 'kcal/mol', '%10.2f'),
        Unit('temperature', 1, 'K', '%10.1f'),
        Unit('length', angstrom, 'A', '%10.4f'),
        Unit('invlength', 1/angstrom, 'A^-1', '%10.5f'),
        Unit('area', angstrom**2, 'A^2', '%10.3f'),
        Unit('volume', angstrom**3, 'A^3', '%10.3f'),
        Unit('time', femtosecond, 'fs', '%10.1f'),
        Unit('mass', amu, 'amu', '%10.5f'),
        Unit('charge', 1, 'e', '%10.5f'),
        Unit('force', kcalmol/angstrom, 'kcal/mol/A', '%10.1f'),
        Unit('forceconst', kcalmol/angstrom**2, 'kcal/mol/A**2', '%10.1f'),
        Unit('velocity', angstrom/femtosecond, 'A/fs', '%10.5f'),
        Unit('acceleration', angstrom/femtosecond**2, 'A/fs**2', '%10.5f'),
        Unit('angle', deg, 'deg', '%10.5f'),
        Unit('c6', 1, 'E_h*a_0**6', '%10.5f'),
        Unit('diffconst', angstrom**2/femtosecond, 'A**2/fs', '%10.5f'),
        Unit('density', gram/centimeter**3, 'g/cm^3', '%10.3f'),
    )
    solid = UnitSystem(
        Unit('energy', electronvolt, 'eV', '%10.4f'),
        Unit('temperature', 1, 'K', '%10.1f'),
        Unit('length', angstrom, 'A', '%10.4f'),
        Unit('invlength', 1/angstrom, 'A^-1', '%10.5f'),
        Unit('area', angstrom**2, 'A^2', '%10.3f'),
        Unit('volume', angstrom**3, 'A^3', '%10.3f'),
        Unit('time', femtosecond, 'fs', '%10.1f'),
        Unit('mass', amu, 'amu', '%10.5f'),
        Unit('charge', 1, 'e', '%10.5f'),
        Unit('force', electronvolt/angstrom, 'eV/A', '%10.1f'),
        Unit('forceconst', electronvolt/angstrom**2, 'eV/A**2', '%10.1f'),
        Unit('velocity', angstrom/femtosecond, 'A/fs', '%10.5f'),
        Unit('acceleration', angstrom/femtosecond**2, 'A/fs**2', '%10.5f'),
        Unit('angle', deg, 'deg', '%10.5f'),
        Unit('c6', 1, 'E_h*a_0**6', '%10.5f'),
        Unit('diffconst', angstrom**2/femtosecond, 'A**2/fs', '%10.5f'),
        Unit('density', gram/centimeter**3, 'g/cm^3', '%10.3f'),
    )
    bio = UnitSystem(
        Unit('energy', kcalmol, 'kcal/mol', '%10.2f'),
        Unit('temperature', 1, 'K', '%10.1f'),
        Unit('length', nanometer, 'nm', '%10.6f'),
        Unit('area', nanometer**2, 'nm^2', '%10.4f'),
        Unit('volume', nanometer**3, 'nanometer^3', '%10.1f'),
        Unit('invlength', 1/nanometer, 'nm^-1', '%10.8f'),
        Unit('time', picosecond, 'ps', '%10.4f'),
        Unit('mass', amu, 'amu', '%10.5f'),
        Unit('charge', 1, 'e', '%10.5f'),
        Unit('force', kcalmol/angstrom, 'kcal/mol/A', '%10.5f'),
        Unit('forceconst', kcalmol/angstrom**2, 'kcal/mol/A**2', '%10.5f'),
        Unit('velocity', angstrom/picosecond, 'A/ps', '%10.5f'),
        Unit('acceleration', angstrom/picosecond**2, 'A/ps**2', '%10.5f'),
        Unit('angle', deg, 'deg', '%10.5f'),
        Unit('c6', 1, 'E_h*a_0**6', '%10.5f'),
        Unit('diffconst', nanometer**2/picosecond, 'nm**2/ps', '%10.2f'),
        Unit('density', gram/centimeter**3, 'g/cm^3', '%10.3f'),
    )
    atomic = UnitSystem(
        Unit('energy', 1, 'E_h', '%10.6f'),
        Unit('temperature', 1, 'K', '%10.1f'),
        Unit('length', 1, 'a_0', '%10.5f'),
        Unit('invlength', 1, 'a_0^-1', '%10.5f'),
        Unit('area', 1, 'a_0^2', '%10.3f'),
        Unit('volume', 1, 'a_0^3', '%10.3f'),
        Unit('time', 1, 'aut', '%10.1f'),
        Unit('mass', 1, 'aum', '%10.1f'),
        Unit('charge', 1, 'e', '%10.5f'),
        Unit('force', 1, 'E_h/a_0', '%10.5f'),
        Unit('forceconst', 1, 'E_h/a_0**2', '%10.5f'),
        Unit('velocity', 1, 'a_0/aut', '%10.5f'),
        Unit('acceleration', 1, 'a_0/aut**2', '%10.5f'),
        Unit('angle', 1, 'rad', '%10.7f'),
        Unit('c6', 1, 'E_h*a_0**6', '%10.5f'),
        Unit('diffconst', 1, 'a_0**2/aut', '%10.2f'),
        Unit('density', 1, 'aum/a_0^3', '%10.3f'),
    )


    def __init__(self, f=None):
        self._active = False
        self._level = self.medium
        self.unitsys = self.joule
        self.unitsys.apply(self)
        self.prefix = ' '*(self.margin-1)
        self._last_used_prefix = None
        self.stack = []
        self.add_newline = False
        if f is None:
            self._file = sys.stdout
        else:
            self._file = f

    do_warning = property(lambda self: self._level >= self.warning)
    do_low = property(lambda self: self._level >= self.low)
    do_medium = property(lambda self: self._level >= self.medium)
    do_high = property(lambda self: self._level >= self.high)
    do_debug = property(lambda self: self._level >= self.debug)

    def set_level(self, level):
        if level < self.silent or level > self.debug:
            raise ValueError('The level must be one of the ScreenLog attributes.')
        self._level = level

    def __call__(self, *words):
        s = ' '.join(str(w) for w in words)
        if not self.do_warning:
            raise RuntimeError('The runlevel should be at least warning when logging.')
        if not self._active:
            timer._start('Total')
            prefix = self.prefix
            self.print_header()
            self.prefix = prefix
        if self.add_newline and self.prefix != self._last_used_prefix:
            print >> self._file
            self.add_newline = False
        # Check for alignment code '&'
        pos = s.find('&')
        if pos == -1:
            lead = ''
            rest = s
        else:
            lead = s[:pos] + ' '
            rest = s[pos+1:]
        width = self.width - len(lead)
        if width < self.width/2:
            raise ValueError('The lead may not exceed half the width of the terminal.')
        # break and print the line
        first = True
        while len(rest) > 0:
            if len(rest) > width:
                pos = rest.rfind(' ', 0, width)
                if pos == -1:
                    current = rest[:width]
                    rest = rest[width:]
                else:
                    current = rest[:pos]
                    rest = rest[pos:].lstrip()
            else:
                current = rest
                rest = ''
            print >> self._file, '%s %s%s' % (self.prefix, lead, current)
            if first:
                lead = ' '*len(lead)
                first = False
        self._last_used_prefix = self.prefix

    def warn(self, *words):
        self('WARNING!!&'+' '.join(words))

    def hline(self, char='~'):
        self(char*self.width)

    def blank(self):
        print >> self._file

    def _enter(self, prefix):
        if len(prefix) > self.margin-1:
            raise ValueError('The prefix must be at most %s characters wide.' % (self.margin-1))
        self.stack.append(self.prefix)
        self.prefix = prefix.upper().rjust(self.margin-1, ' ')
        self.add_newline = True

    def _exit(self):
        self.prefix = self.stack.pop(-1)
        if self._active:
            self.add_newline = True

    @contextmanager
    def section(self, prefix):
        self._enter(prefix)
        try:
            yield
        finally:
            self._exit()

    def set_unitsys(self, unitsys):
        self.unitsys = unitsys
        self.unitsys.apply(self)
        if self._active:
            self.unitsys.log_info()

    def print_header(self):
        if self.do_warning and not self._active:
            self._active = True
            print >> self._file, head_banner
            self._print_basic_info()
            self.unitsys.log_info()

    def print_footer(self):
        if self.do_warning and self._active:
            self._print_basic_info()
            timer._stop()
            timer.report(self)
            print >> self._file, foot_banner

    def _print_basic_info(self):
        if log.do_low:
            import yaff
            with log.section('ENV'):
                log('User:          &' + getpass.getuser())
                log('Machine info:  &' + ' '.join(os.uname()))
                log('Time:          &' + datetime.datetime.now().isoformat())
                log('Python version:&' + sys.version.replace('\n', ''))
                log('YAFF version:  &' + yaff.__version__)
                log('Current Dir:   &' + os.getcwd())
                log('Command line:  &' + ' '.join(sys.argv))


log = ScreenLog()
atexit.register(log.print_footer)
