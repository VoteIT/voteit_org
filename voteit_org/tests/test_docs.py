import voteit_org
from voteit.core.testing import load_doctests


def load_tests(loader, tests, pattern):
    load_doctests(tests, voteit_org)
    return tests
