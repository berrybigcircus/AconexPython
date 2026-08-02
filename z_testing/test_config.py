from unittest import TestCase

import pytest

from Setup import EAsetup, UK1setup
from Setup.config import *
from Setup.config import get_modification_time


class TestConfig(TestCase):
    def init_ea(self):
        init(EAsetup.bearer, EAsetup.env, debug=["HB Test", "1879048648", "HBT"])

    def init_WPS(self):
        init(UK1setup.bearer, UK1setup.env, debug=["Wolverhampton Police", "268456307", "WPS"])

    def init_JFW(self):
        init(UK1setup.bearer, UK1setup.env, debug=["Northampton JAWS", "268459784", "JFW"])

    def init_MTP(self):
        init(UK1setup.bearer, UK1setup.env, debug=["MTP", "268457782", "MTP"])

    def init_UTC(self):
        init(UK1setup.bearer, UK1setup.env, debug=["LRI UTC", "268457466", "UTC"])

    def init_9910(self):
        init(UK1setup.bearer, UK1setup.env, debug=["HMCTS Nottingham", "268458266", "9910"])

    def init_A5057(self):
        init(UK1setup.bearer, UK1setup.env, debug=["Belper Health Hub", "268456352", "A5057"])

    def init_CDC(self):
        init(UK1setup.bearer, UK1setup.env, debug=["NUHT CDC", "268456728", "CDC"])

    def init_CMUH(self):
        init(UK1setup.bearer, UK1setup.env, debug=["MMUH UTC", "268459077", "020261"])

    def create(self) -> Config:
        self.init_ea()
        assert Config()
        assert config.logger
        assert config.bearer() == EAsetup.bearer
        assert config.env() == EAsetup.env
        assert config.projectname() == "HB Test"
        assert config.project

        return config

    def test_init(self):
        self.init_ea()
        assert Config()

    @pytest.mark.integration
    def test_get_modification_time(self):
        filepath = r"C:\Users\nicole.millinship\PycharmProjects\AconexPython\b_Workflow\Trackers\JFW - Workflow Tracker.xlsx"

        print(get_modification_time(filepath))

