from unittest import TestCase

import pytest

from Setup.APIcommon import loadCookies
from Setup.config import Config
from z_testing.test_config import TestConfig


class TestCommon(TestCase):
    @pytest.mark.integration
    def test_load_cookies(self):
        tconfig = TestConfig()
        config : Config = tconfig.create()
        a, b = loadCookies(config)
        assert a
        assert b