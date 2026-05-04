from unittest import TestCase

from Setup import EAsetup
from Setup.config import *

class TestConfig(TestCase):
    def init_ea(self):
        init(EAsetup.bearer, EAsetup.env, debug=["HB Test", "1879048648", "HBT"])

    def test_create(self):
        self.init_ea()
        assert Config()
        assert config.logger
        assert config.bearer() == EAsetup.bearer
        assert config.env() == EAsetup.env
        assert config.projectname() == "HB Test"
        assert config.project

        return config