from unittest import TestCase

import pytest

from Setup.APIcommon import loadCookies, SelLogIn
from Setup.config import config
from z_testing.test_config import TestConfig


class TestCommon(TestCase):
    @pytest.mark.integration
    def test_load_cookies(self):
        tconfig = TestConfig()
        tconfig.init_UTC()
        a, b = loadCookies(config)
        assert a
        assert b

    @pytest.mark.integration
    def test_sel_login(self):
        tconfig = TestConfig()
        tconfig.init_UTC()
        SelLogIn(config)
