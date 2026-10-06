import datetime
import os
from unittest import TestCase

import pytest

from Setup.Doc import search_for_tracker
from Setup.Outlook import initProject, autorunWFComments
from Setup.config import config, refreshTracker
from b_Workflow.WorkflowComments import uploadWFTracker, main, clear_workflowdata, addWorkflowData, \
    workflowData, getAllWorkflows
from z_testing.test_config import TestConfig


class TestWF:
    @pytest.mark.integration
    def wftrackerpath(self):
        exp_filepath = config.project().getWFExportDataLocation()
        assert os.path.exists(exp_filepath)
        tracker_filepath = exp_filepath.replace("ExportedData.xlsx", "Workflow Tracker.xlsx")
        return tracker_filepath

    @pytest.mark.integration
    def test_search_tracker(self):
        tconfig = TestConfig()
        tconfig.init_CMUH()
        docnumber = config.project().getWFTrackerNumber()
        dategen = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
        search_for_tracker(config, config.project().getWFExportDataLocation(), docnumber, dategen, silent=False)


    @pytest.mark.integration
    #upload only, no refresh
    def test_upload_wftracker(self):
        tconfig = TestConfig()
        tconfig.init_SPR()
        assert uploadWFTracker(config, self.wftrackerpath(), True)

    @pytest.mark.integration
    def test_throttle_upload(self, caplog):
        self.test_upload_wftracker()
        self.test_upload_wftracker()
        assert caplog.records[-1].message != "Failed to supersede"


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

        assert uploadWFTracker(config, self.wftrackerpath(), False)

    @pytest.mark.integration
    #Test full wf tracker update, refresh and upload
    def test_run_WFTracker(self):
        tconfig = TestConfig()
        
        tconfig.init_JFW()

        assert main(inputUseTextFile="n", forceAll=True) == True

    def test_clear_wfdata(self):
        tconfig = TestConfig()
        tconfig.init_JFW()

        addWorkflowData(getAllWorkflows())
        clear_workflowdata()
        assert workflowData["Document Number"] == []

    @pytest.mark.integration
    def test_autorun(self):
        projects = ["MMUH UTC", "NUHT CDC"]
        for projectname in projects:
            initProject(projectname, "projectnames", False)
            success = autorunWFComments(False, projectname)
            if projectname == "Wolverhampton Police":
                assert config.project().projectName() == "Wolverhampton Police"
                assert config.project().getWFPickleLocation().endswith("WPS - mails.pkl")
                assert config.project().getWFExportDataLocation().endswith("WPS - ExportedData.xlsx")
                assert workflowData["Document Number"] == []
            assert success


    #TODO
    @pytest.mark.integration
    def upload_all_WF_Trackers(self):
        tconfig = TestConfig()
        tconfig.init_JFW()

        exp_filepath = config.project().getWFExportDataLocation()
        tracker_filepath = exp_filepath.replace("ExportedData.xlsx", "Workflow Tracker.xlsx")
        search_for_tracker(config, tracker_filepath, config.project().getWFTrackerNumber(), dategen="")