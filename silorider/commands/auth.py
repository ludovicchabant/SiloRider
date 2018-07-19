import logging
from ..silos.base import SiloAuthenticationContext


logger = logging.getLogger(__name__)


def auth_silo(ctx):
    silo_names = ctx.args.silo
    if 'all' in silo_names:
        silo_names = [s.name for s in ctx.silos]

    for silo in ctx.silos:
        if silo.name not in silo_names:
            continue

        logger.debug("Authenticating silo: %s" % silo.name)
        authctx = SiloAuthenticationContext(ctx)
        silo.authenticate(authctx)
