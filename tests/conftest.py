import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def english():
    """Tests assert English messages unless they switch language themselves."""
    from core.i18n import set_language
    set_language("en")
    yield
    set_language("en")
