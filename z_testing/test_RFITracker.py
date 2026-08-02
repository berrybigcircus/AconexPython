import os
from unittest import TestCase

import pytest

from Setup.Doc import search_for_tracker
from Setup.Mail import AconexThread
from Setup.config import config, refreshTracker
from d_Mail.RFIs.RFITracker import uploadRFITracker, main, getrfithreadnew
from z_testing.test_config import TestConfig


class TestRFI(TestCase):
    @pytest.mark.integration
    def rfitrackerpath(self):
        exp_filepath = config.project().getRFITrackerLocation()
        assert os.path.exists(exp_filepath)
        tracker_filepath = exp_filepath.replace("Exported Data.xlsx", "RFI Tracker.xlsx")
        return tracker_filepath

    @pytest.mark.integration
    def test_upload_rfitracker(self):
        tconfig = TestConfig()
        tconfig.init_MTP()

        assert uploadRFITracker(config, self.rfitrackerpath(), True) != False

    @pytest.mark.integration
    def test_refresh_rfitracker(self):
        tconfig = TestConfig()
        tconfig.init_MTP()

        dategen = refreshTracker(self.rfitrackerpath(), accept_time_diff=True)
        assert type(dategen) == str

    @pytest.mark.integration
    def test_refresh_and_upload(self):
        tconfig = TestConfig()
        tconfig.init_MTP()

        assert uploadRFITracker(config, self.rfitrackerpath(), False) != False

    @pytest.mark.integration
    # Test full  tracker update, refresh and upload
    def test_run_RFITracker(self):
        tconfig = TestConfig()

        tconfig.init_CMUH()

        assert main() == True

    def test_getRFIs(self):
        tconfig = TestConfig()
        tconfig.init_CMUH()

        getrfithreadnew(loadpickle=False, lastrun=None)

    def test_mailthread(self):
        tconfig = TestConfig()

        tconfig.init_CMUH()
        athread = AconexThread(config, "351620320")
        print(athread.refno)
        athread.root.debug()
        athread.latestmail.debug()
        athread.latestmail.ParentMail.debug()


    def test_formfields(self):
        tconfig = TestConfig()
        tconfig.init_CMUH()

        mailtypes = config.mailtypes()

        adminerrormail = list(filter(lambda m : m.typename()=="Admin Error", mailtypes))[0]

        ae_ff = adminerrormail.projectfields()
        print(ae_ff)

        athread = AconexThread(config, "351620320")
        athread.root.debug()
        print(athread.root.getFormFieldVal("RFI Description"))






