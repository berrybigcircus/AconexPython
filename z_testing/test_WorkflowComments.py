import os
import string
from unittest import TestCase

import pytest

from Setup.Doc import search_for_tracker
from Setup.config import config, refreshTracker
from b_Workflow.WorkflowComments import uploadWFTracker, main
from z_testing.test_config import TestConfig


class TestWF(TestCase):

    def wftrackerpath(self):
        exp_filepath = config.project().getWFExportDataLocation()
        assert os.path.exists(exp_filepath)
        tracker_filepath = exp_filepath.replace("ExportedData.xlsx", "Workflow Tracker.xlsx")
        return tracker_filepath

    @pytest.mark.integration
    #upload only, no refresh
    def test_upload_wftracker(self):
        tconfig = TestConfig()
        tconfig.init_WPS()

        assert uploadWFTracker(config, self.wftrackerpath(), True) != False

    @pytest.mark.integration
    #refresh then upload
    def test_refresh_wftracker(self):
        tconfig = TestConfig()
        tconfig.init_WPS()

        dategen = refreshTracker(self.wftrackerpath(), accept_time_diff=True)
        assert type(dategen) == str

    @pytest.mark.integration
    def test_refresh_and_upload(self):
        tconfig = TestConfig()
        tconfig.init_JFW()

        assert uploadWFTracker(config, self.wftrackerpath(), False) != False

    @pytest.mark.integration
    #Test full wf tracker update, refresh and upload
    def test_run_WFTracker(self):
        tconfig = TestConfig()
        
        tconfig.init_JFW()

        assert main(inputUseTextFile="n", forceAll=True) == True


    #TODO
    @pytest.mark.integration
    def upload_all_WF_Trackers(self):
        tconfig = TestConfig()
        tconfig.init_JFW()

        exp_filepath = config.project().getWFExportDataLocation()
        tracker_filepath = exp_filepath.replace("ExportedData.xlsx", "Workflow Tracker.xlsx")
        search_for_tracker(config, tracker_filepath, config.project().getWFTrackerNumber(), dategen="")