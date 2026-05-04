from unittest import TestCase

from Setup.APIcommon import loadCookies
from Setup.config import Config
from z_testing.test_config import TestConfig


class TestCommon(TestCase):
    def test_load_cookies(self):
        tconfig = TestConfig()
        config : Config = tconfig.test_create()
        a, b = loadCookies(config)
        assert a
        assert b