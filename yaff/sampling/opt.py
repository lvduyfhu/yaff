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


import numpy as np, time

from molmod.minimizer import ConjugateGradient, QuasiNewton, NewtonLineSearch, \
    Minimizer

from yaff.log import log
from yaff.sampling.iterative import Iterative, AttributeStateItem, \
    PosStateItem, DipoleStateItem, VolumeStateItem, CellStateItem, \
    EPotContribStateItem, Hook


__all__ = [
    'OptScreenLog', 'BaseOptimizer', 'CGOptimizer', 'BFGSHessianModel',
    'BFGSOptimizer',
]


class OptScreenLog(Hook):
    def __init__(self, start=0, step=1):
        Hook.__init__(self, start, step)
        self.time0 = None

    def __call__(self, iterative):
        if log.do_medium:
            if self.time0 is None:
                self.time0 = time.time()
                if log.do_medium:
                    log.hline()
                    log('Conv.val. =&the highest ratio of a convergence criterion over its threshold.')
                    log('N         =&the number of convergence criteria that is not met.')
                    log('Worst     =&the name of the convergence criterion that is worst.')
                    log('counter  Conv.val.  N        Worst   Walltime')
                    log.hline()
            log('%7i % 10.3e %2i %12s %10.1f' % (
                iterative.counter,
                iterative.dof.conv_val,
                iterative.dof.conv_count,
                iterative.dof.conv_worst,
                time.time() - self.time0,
            ))


class BaseOptimizer(Iterative):
    # TODO: This should be copied upon initialization. As it is now, two
    # consecutive simulations with a different number of atoms will raise an
    # exception.
    default_state = [
        AttributeStateItem('counter'),
        AttributeStateItem('epot'),
        PosStateItem(),
        DipoleStateItem(),
        VolumeStateItem(),
        CellStateItem(),
        EPotContribStateItem(),
    ]
    log_name = 'XXOPT'

    def __init__(self, dof, state=None, hooks=None, counter0=0):
        """
           **Arguments:**

           dof
                A specification of the degrees of freedom. The convergence
                criteria are also part of this argument. This must be a DOF
                instance.

           **Optional arguments:**

           state
                A list with state items. State items are simple objects
                that take or derive a property from the current state of the
                iterative algorithm.

           hooks
                A function (or a list of functions) that is called after every
                iterative.

           counter0
                The counter value associated with the initial state.
        """
        self.dof = dof
        Iterative.__init__(self, dof.ff, state, hooks, counter0)

    def _add_default_hooks(self):
        if not any(isinstance(hook, OptScreenLog) for hook in self.hooks):
            self.hooks.append(OptScreenLog())

    def fun(self, x, do_gradient=False):
        if do_gradient:
            self.epot, gx = self.dof.fun(x, True)
            return self.epot, gx
        else:
            self.epot = self.dof.fun(x, False)
            return self.epot

    def initialize(self):
        # The first call to check_convergence will never flag convergence, but
        # it is need to keep track of some convergence criteria.
        self.dof.check_convergence()
        Iterative.initialize(self)

    def propagate(self):
        self.dof.check_convergence()
        Iterative.propagate(self)
        return self.dof.converged

    def finalize(self):
        if log.do_medium:
            log.hline()


class CGOptimizer(BaseOptimizer):
    log_name = 'CGOPT'

    def __init__(self, dof, state=None, hooks=None, counter0=0):
        self.minimizer = Minimizer(
            dof.x0, self.fun, ConjugateGradient(), NewtonLineSearch(), None,
            None, anagrad=True, verbose=False,
        )
        BaseOptimizer.__init__(self, dof, state, hooks, counter0)

    def initialize(self):
        self.minimizer.initialize()
        BaseOptimizer.initialize(self)

    def propagate(self):
        success = self.minimizer.propagate()
        self.x = self.minimizer.x
        if success == False:
            if log.do_warning:
                log.warn('Line search failed in optimizer. Aborting optimization. This is probably due to a dicontinuity in the energy or the forces. Check the truncation of the non-bonding interactions and the Ewald summation parameters.')
            return True
        return BaseOptimizer.propagate(self)


class BFGSHessianModel(object):
    def __init__(self, size):
        self.hessian = np.identity(size, float)

    def update(self, dx, dg):
        tmp = np.dot(self.hessian, dx)
        hmax = abs(self.hessian).max()
        # Only compute updates if the denominators do not blow up
        denom1 = np.dot(dx, tmp)
        if hmax*denom1 <= 1e-5*abs(tmp).max():
            if log.do_high:
                log('Skipping BFGS update because denom1=%10.3e is not positive enough.' % denom1)
            return
        denom2 = np.dot(dg, dx)
        if hmax*denom2 <= 1e-5*abs(dg).max():
            if log.do_high:
                log('Skipping BFGS update because denom2=%10.3e is not positive enough.' % denom2)
            return
        if log.do_debug:
            log('Updating BFGS Hessian.    denom1=%10.3e   denom2=%10.3e' % (denom1, denom2))
        self.hessian -= np.outer(tmp, tmp)/denom1
        self.hessian += np.outer(dg, dg)/denom2

    def get_spectrum(self):
        return np.linalg.eigh(self.hessian)


class BFGSOptimizer(BaseOptimizer):
    """BFGS optimizer

       This is just a basic implementation of the algorithm, but it has the
       potential to become more advanced and efficient. The following
       improvements will be made when time permits:

       1) Support for non-linear constraints. This should be relatively easy. We
          need a routine that can bring the unknowns back to the constraints,
          and a routine to solve a constrained second order problem with linear
          equality/inequality constraints. These should be methods of an object
          that is an attribute of the dof object, which is need to give the
          constraint code access to the Cartesian coordinates. In the code
          below, some comments are added to mark where the constraint methods
          should be called.

       2) The Hessian updates and the diagonalization are currently very slow
          for big systems. This can be fixed with a rank-1 update algorithm for
          the spectral decomposition.

       3) The optimizer would become much more efficient if redundant
          coordinates were used. This can be implemented efficiently by using
          the same machinery as the constraint code, but using the dlist and
          iclist concepts for the sake of efficiency.

       4) It is in practice not needed to keep track of the full Hessian. The
          L-BFGS algorithm is a nice method to obtain a linear memory usage and
          computational cost. However, L-BFGS is not compatible with the trust
          radius used in this class, while we want to keep the trust radius for
          the sake of efficiency, robustness and support for constraints. Using
          the rank-1 updates mentioned above, it should be relatively easy to
          keep track of the decomposition of a subspace of the Hessian.
          This subspace can be defined as the basis of the last N rank-1
          updates. Simple assumptions about the remainder of the spectrum should
          be sufficient to keep the algorithm efficient.
    """
    log_name = 'BFGSOPT'

    def __init__(self, dof, state=None, hooks=None, counter0=0, small_radius=1e-5):
        """
           **Arguments:**

           dof
                A specification of the degrees of freedom. The convergence
                criteria are also part of this argument. This must be a DOF
                instance.

           **Optional arguments:**

           state
                A list with state items. State items are simple objects
                that take or derive a property from the current state of the
                iterative algorithm.

           hooks
                A function (or a list of functions) that is called after every
                iterative.

           counter0
                The counter value associated with the initial state.

           small_radius
                If the trust radius goes below this limit, the decrease in
                energy is no longer essential. Instead a decrease in the norm
                of the gradient is used to accept/reject a step.
        """
        self.x_old = dof.x0
        self.hessian = BFGSHessianModel(len(dof.x0))
        self.trust_radius = 1.0
        self.small_radius = small_radius
        BaseOptimizer.__init__(self, dof, state, hooks, counter0)

    def initialize(self):
        self.f_old, self.g_old = self.fun(self.dof.x0, True)
        self.x, self.f, self.g = self.make_step()
        BaseOptimizer.initialize(self)

    def propagate(self):
        # Update the Hessian
        assert not self.g is self.g_old
        assert not self.x is self.x_old
        self.hessian.update(self.x - self.x_old, self.g - self.g_old)
        # Move new to old
        self.x_old = self.x
        self.f_old = self.f
        self.g_old = self.g
        # Compute a step
        self.x, self.f, self.g = self.make_step()
        return BaseOptimizer.propagate(self)

    def make_step(self):
        evals, evecs = self.hessian.get_spectrum()
        tmp1 = -np.dot(evecs.T, self.g_old)

        # Initial ridge parameter
        if evals.min() <= 0:
            # Make the ridge large enough to step in a direction opposite to the
            # gradient.
            ridge = abs(evals.min())*1.1
        else:
            ridge = 0.0

        # Trust radius loop
        if log.do_high:
            log.hline()
            log('       Ridge      Radius       Trust')
            log.hline()
        while True:
            # Increase ridge until step is smaller than trust radius
            while True:
                # MARKER FOR CONSTRAINT CODE: instead of the following line, a
                # constrained harmonic solver should be added to find the step
                # that minimizes the local quadratic problem under a set of linear
                # equality/inequality constraints. This can be implemented using
                # the active set algorithm.
                tmp2 = tmp1*evals/(evals**2 + ridge**2)
                radius = np.linalg.norm(tmp2)
                if log.do_high:
                    log('%12.5e %12.5e %12.5e' % (ridge, radius, self.trust_radius))
                if radius < self.trust_radius:
                    break
                if ridge == 0.0:
                    ridge = abs(evals[evals!=0.0]).min()
                else:
                    ridge *= 1.2
            # Check if the step is trust worthy
            delta_x = np.dot(evecs, tmp2)
            # MARKER FOR CONSTRAINT CODE: the following line should be replaced
            # by something of the sort:
            # x = self.shaker.fix(self.x_old + delta_x)
            x = self.x_old + delta_x
            f, g = self.fun(x, True)
            # MARKER FOR CONSTRAINT CODE: project the gradient.
            delta_f = f - self.f_old
            delta_norm_g = np.linalg.norm(g) - np.linalg.norm(self.g_old)
            if delta_f > 0 or (self.trust_radius < self.small_radius and delta_norm_g < 0):
                # The function must decrease, if not the trust radius is too big.
                # This is similar to the first Wolfe condition. When the trust
                # radius becomes small, the numerical noise on the energy may
                # be too large to detect a decrease in energy. In that case,
                # the norm of the gradient must decrease.
                if log.do_high:
                    log('Function (or grad norm) increases.')
                self.trust_radius *= 0.5
                continue
            # MARKER FOR CONSTRAINT CODE: the following should be ignored if
            # the number of active constraints changes. In case of any
            # constraints, delta_x should be updated.
            if np.dot(delta_x, g) > 0:
                # This means that we ended up too far at the other end of the
                # minimum. Note that this is intentionally very different from
                # the second Wolfe condition. Keep in mind that this optimizer
                # does not use line searches.
                if log.do_high:
                    log('dot(new gradient, step) > 0.')
                self.trust_radius *= 0.5
                continue
            # If we get here, we are done.
            if log.do_high:
                log.hline()
            self.trust_radius *= 1.2
            return x, f, g
