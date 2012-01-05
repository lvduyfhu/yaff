# YAFF is yet another force-field code
# Copyright (C) 2008 - 2012 Toon Verstraelen <Toon.Verstraelen@UGent.be>, Center
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


import numpy as np

from yaff.log import log


__all__ = ['Scalings', 'iter_paths']


scaling_dtype = [('a', int), ('b', int), ('scale', float), ('nbond', int)]


class Scalings(object):
    def __init__(self, system, scale1=0.0, scale2=0.0, scale3=1.0):
        self.items = []
        if scale1 < 0 or scale1 > 1:
            raise ValueError('scale1 must be in the range [0,1].')
        if scale2 < 0 or scale2 > 1:
            raise ValueError('scale1 must be in the range [0,1].')
        if scale3 < 0 or scale3 > 1:
            raise ValueError('scale1 must be in the range [0,1].')
        self.scale1 = scale1
        self.scale2 = scale2
        self.scale3 = scale3
        stab = []
        for i0 in xrange(system.natom):
            if scale1 < 1.0:
                for i1 in system.neighs1[i0]:
                    if i0 > i1:
                        stab.append((i0, i1, scale1, 1))
            if scale2 < 1.0:
                for i2 in system.neighs2[i0]:
                    if i0 > i2:
                        stab.append((i0, i2, scale2, 2))
            if scale3 < 1.0:
                for i3 in system.neighs3[i0]:
                    if i0 > i3:
                        stab.append((i0, i3, scale3, 3))
        stab.sort()
        self.stab = np.array(stab, dtype=scaling_dtype)
        self.check_mic(system)

    def check_mic(self, system):
        '''Check if each scale2 and scale3 is uniquely defined.

           **Arguments:**

           system
                An instance of the system class, i.e. the one that is used to
                create this scaling object.

           This is done by constructing for each scaled pair, all possible bond
           paths between the two atoms. For each path, the bond vectors (after
           applying the minimum image convention) are added. If for a give pair,
           these sums of bond vectors are different, the difference is expanded
           in cell vectors which can be used to construct a proper supercell in
           which scale2 and scale3 pairs are all uniquely defined.
        '''
        if system.cell.nvec == 0:
            return
        troubles = False
        with log.section('SCALING'):
            for i0, i1, scale, nbond in self.stab:
                if nbond == 1:
                    continue
                all_deltas = []
                paths = []
                for path in iter_paths(system, i0, i1, nbond):
                    delta_total = 0
                    for j0 in xrange(nbond):
                        j1 = j0 + 1
                        delta = system.pos[path[j0]] - system.pos[path[j1]]
                        system.cell.mic(delta)
                        delta_total += delta
                    all_deltas.append(delta_total)
                    paths.append(path)
                all_deltas = np.array(all_deltas)
                if abs(all_deltas.mean(axis=0) - all_deltas).max() > 1e-10:
                    troubles = True
                    if log.do_warning:
                        log.warn('Troublesome pair scaling detected.')
                    log('The following bond paths connect the same pair of '
                        'atoms, yet the relative vectors are different.')
                    for ipath in xrange(len(paths)):
                        log('%2i %27s %10s %10s %10s' % (
                            ipath,
                            ','.join(str(index) for index in paths[ipath]),
                            log.length(all_deltas[ipath,0]),
                            log.length(all_deltas[ipath,1]),
                            log.length(all_deltas[ipath,2]),
                        ))
                    log('Differences between relative vectors in fractional '
                        'coordinates:')
                    for ipath0 in xrange(1, len(paths)):
                        for ipath1 in xrange(ipath0):
                            diff = all_deltas[ipath0] - all_deltas[ipath1]
                            diff_frac = np.dot(system.cell.gvecs, diff)
                            log('%2i %2i %10.4f %10.4f %10.4f' % (
                                ipath0, ipath1,
                                diff_frac[0], diff_frac[1], diff_frac[2]
                            ))
                    log.blank()
        if troubles:
            # TODO: in a distant future it may be worth the trouble to
            # reimplement the pair scaling such that these cases are handeled
            # gracefully.
            raise AssertionError('Due to the small spacing between some crystal planes, the scaling of non-bonding interactions will not work properly. Use a supercell to avoid this problem.')


def iter_paths(system, ib, ie, nbond):
    """Iterates over all paths between ib and ie with the given number of bonds"""
    if nbond == 1:
        if ie in system.neighs1[ib]:
            yield (ib, ie)
    else:
        for i1 in system.neighs1[ib]:
            for path in iter_paths(system, i1, ie, nbond-1):
                if ib not in path:
                    yield (ib,) + path
