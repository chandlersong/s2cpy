"""Pytest configuration helpers for this project.

When tests are run with -m manual, we want the test run to use the "dev"
configuration by default. This file sets ENV=dev when the -m expression
includes the "manual" marker (but does not override an explicitly set
ENV environment variable).
"""
import os
import re


def pytest_configure(config):
    """Called after command line options have been parsed.

    If the user passed `-m manual` (or a mark expression containing the
    token `manual`) we set ENV=dev unless ENV is already set.
    """
    markexpr = getattr(config.option, "markexpr", "") or ""
    # Look for the standalone word `manual` in the -m expression.
    if markexpr and re.search(r"\bmanual\b", markexpr):
        # Do not overwrite an explicitly provided ENV
        os.environ["ENV"] = "dev"

        # Notify the user in pytest output so it's obvious which config is active
        try:
            tr = config.pluginmanager.getplugin("terminalreporter")
            if tr is not None:
                tr.write_line("pytest: detected -m manual -> set ENV=dev")
            else:
                print("pytest: detected -m manual -> set ENV=dev")
        except Exception:
            # Be silent if anything goes wrong writing to the reporter
            pass
