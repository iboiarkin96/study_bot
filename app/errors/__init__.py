"""Central catalog of stable API error codes.

Import concrete identities from :mod:`app.errors.common` and :mod:`app.errors.user`
(or :class:`~app.errors.types.StableError`) instead of scattering string literals.

Validation mapping dicts live in :mod:`app.errors.user` and are consumed by
:mod:`app.validation`.
"""

from app.errors.types import StableError

__all__ = ["StableError"]
