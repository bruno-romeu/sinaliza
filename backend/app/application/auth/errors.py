class InvalidCredentialsError(Exception):
    """Raised by `AuthenticateUserService` on any mismatch — unknown email or
    wrong password. Deliberately carries no detail about which one failed, so
    the presentation layer can map it to one identical, factual message and
    prevent user enumeration (RNF-05, spec I/O Matrix)."""
