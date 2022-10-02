import numpy as np
import scipy.stats as osp_stats

from jax import lax
from jax._src.lax.lax import _const as _lax_const
from jax._src.numpy import lax_numpy as jnp
from jax._src.numpy.util import _wraps
from jax._src.numpy.lax_numpy import _promote_args_inexact
from jax.scipy import special, stats


def _log_diff(x, y):
    return special.logsumexp([x, y], b=[1, -1], axis=0)


def _log_gauss_mass(a, b):
    """a,b here are standard normal limits, i.e., if you clip at values my_a, my_b:
        a = (my_a - mean) / std
        b = (my_b - mean) / std

    Unlike in scipy, a and b have to be scalars
    """

    # Calculations in right tail are inaccurate, so we'll exploit the
    # symmetry and work only in the left tail
    case_left = b <= 0
    case_right = a > 0
    case_central = ~(case_left | case_right)

    def mass_case_left(a, b):
        return _log_diff(special.log_ndtr(b), special.log_ndtr(a))

    def mass_case_right(a, b):
        return mass_case_left(-b, -a)

    def mass_case_central(a, b):
        # Previously, this was implemented as:
        # left_mass = mass_case_left(a, 0)
        # right_mass = mass_case_right(0, b)
        # return _log_sum(left_mass, right_mass)
        # Catastrophic cancellation occurs as np.exp(log_mass) approaches 1.
        # Correct for this with an alternative formulation.
        # We're not concerned with underflow here: if only one term
        # underflows, it was insignificant; if both terms underflow,
        # the result can't accurately be represented in logspace anyway
        # because sc.log1p(x) ~ x for small x.
        return jnp.log1p(-special.ndtr(a) - special.ndtr(-b))

    if case_left:
        out = mass_case_left(a, b)
    elif case_right:
        out = mass_case_right(a, b)
    elif case_central:
        out = mass_case_central(a, b)
    else:
        out = np.nan
    return jnp.real(out)  # discard ~0j


@_wraps(osp_stats.truncnorm.logpdf, update_doc=False)
def logpdf(x, loc=0, scale=1, a=-np.inf, b=np.inf):
    x, loc, scale, a, b = _promote_args_inexact("truncnorm.logpdf", x, loc, scale, a, b)
    return lax.sub(stats.norm.logpdf(x, loc, scale), _log_gauss_mass(a, b))


@_wraps(osp_stats.norm.pdf, update_doc=False)
def pdf(x, loc=0, scale=1, a=-np.inf, b=np.inf):
    return lax.exp(logpdf(x, loc, scale, a, b))


# @_wraps(osp_stats.norm.cdf, update_doc=False)
# def cdf(x, loc=0, scale=1):
#   x, loc, scale = _promote_args_inexact("norm.cdf", x, loc, scale)
#   return special.ndtr(lax.div(lax.sub(x, loc), scale))


# @_wraps(osp_stats.norm.logcdf, update_doc=False)
# def logcdf(x, loc=0, scale=1):
#   x, loc, scale = _promote_args_inexact("norm.logcdf", x, loc, scale)
#   return special.log_ndtr(lax.div(lax.sub(x, loc), scale))


# @_wraps(osp_stats.norm.ppf, update_doc=False)
# def ppf(q, loc=0, scale=1):
#   return jnp.asarray(special.ndtri(q) * scale + loc, float)
