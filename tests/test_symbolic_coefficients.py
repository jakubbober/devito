import numpy as np
import sympy as sp
import pytest

from devito import (Grid, Function, TimeFunction, Eq, Coefficient, Substitutions,
                    Dimension, solve, Operator)
from devito.finite_differences import Differentiable
from devito.tools import as_tuple

_PRECISION = 9


class TestSC(object):
    """
    Class for testing symbolic coefficients functionality
    """

    @pytest.mark.parametrize('order', [1, 2, 6])
    def test_default_rules(self, order):
        """
        Test that the default replacement rules return the same
        as standard FD.
        """
        grid = Grid(shape=(20, 20))
        u0 = TimeFunction(name='u', grid=grid, time_order=order, space_order=order)
        u1 = TimeFunction(name='u', grid=grid, time_order=order, space_order=order,
                          coefficients='symbolic')
        eq0 = Eq(-u0.dx+u0.dt)
        eq1 = Eq(u1.dt-u1.dx)
        assert(eq0.evalf(_PRECISION).__repr__() == eq1.evalf(_PRECISION).__repr__())

    @pytest.mark.parametrize('expr, sorder, dorder, dim, weights, expected', [
        ('u.dx', 2, 1, 0, (-0.6, 0.1, 0.6),
         '0.1*u(x, y) - 0.6*u(x - h_x, y) + 0.6*u(x + h_x, y)'),
        ('u.dy2', 3, 2, 1, (0.121, -0.223, 1.648, -2.904),
         '1.648*u(x, y) + 0.121*u(x, y - 2*h_y) - 0.223*u(x, y - h_y) \
- 2.904*u(x, y + h_y)')])
    def test_coefficients(self, expr, sorder, dorder, dim, weights, expected):
        """Test that custom coefficients return the expected result"""
        grid = Grid(shape=(10, 10))
        u = Function(name='u', grid=grid, space_order=sorder, coefficients='symbolic')
        x = grid.dimensions

        order = dorder
        dim = x[dim]
        weights = np.array(weights)

        coeffs = Coefficient(order, u, dim, weights)

        eq = Eq(eval(expr), coefficients=Substitutions(coeffs))
        assert isinstance(eq.lhs, Differentiable)
        assert expected == str(eq.evaluate.lhs)

    def test_function_coefficients(self):
        """Test that custom function coefficients return the expected result"""
        so = 2
        grid = Grid(shape=(4, 4))
        f0 = TimeFunction(name='f0', grid=grid, space_order=so, coefficients='symbolic')
        f1 = TimeFunction(name='f1', grid=grid, space_order=so)
        x, y = grid.dimensions

        s = Dimension(name='s')
        ncoeffs = so+1

        wshape = list(grid.shape)
        wshape.append(ncoeffs)
        wshape = as_tuple(wshape)

        wdims = list(grid.dimensions)
        wdims.append(s)
        wdims = as_tuple(wdims)

        w = Function(name='w', dimensions=wdims, shape=wshape)
        w.data[:, :, 0] = 0.0
        w.data[:, :, 1] = -1.0/grid.spacing[0]
        w.data[:, :, 2] = 1.0/grid.spacing[0]

        f_x_coeffs = Coefficient(1, f0, x, w)

        subs = Substitutions(f_x_coeffs)

        eq0 = Eq(f0.dt + f0.dx, 1, coefficients=subs)
        eq1 = Eq(f1.dt + f1.dx, 1)

        stencil0 = solve(eq0.evaluate, f0.forward)
        stencil1 = solve(eq1.evaluate, f1.forward)

        op0 = Operator(Eq(f0.forward, stencil0))
        op1 = Operator(Eq(f1.forward, stencil1))

        op0(time_m=0, time_M=5, dt=1.0)
        op1(time_m=0, time_M=5, dt=1.0)

        assert np.all(np.isclose(f0.data[:] - f1.data[:], 0.0, atol=1e-5, rtol=0))

    def test_coefficients_w_xreplace(self):
        """Test custom coefficients with an xreplace before they are applied"""
        grid = Grid(shape=(4, 4))
        u = Function(name='u', grid=grid, space_order=2, coefficients='symbolic')
        x = grid.dimensions[0]

        dorder = 1
        weights = np.array([-0.6, 0.1, 0.6])

        coeffs = Coefficient(dorder, u, x, weights)

        c = sp.Symbol('c')

        eq = Eq(u.dx+c, coefficients=Substitutions(coeffs))
        eq = eq.xreplace({c: 2})

        expected = '0.1*u(x, y) - 0.6*u(x - h_x, y) + 0.6*u(x + h_x, y) + 2'

        assert expected == str(eq.evaluate.lhs)
