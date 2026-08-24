from unittest import TestCase
from unittest.mock import patch

import pytest

from Setup.config import config
from a_Directory import Directory, Directory_UI
from a_Directory.Directory import cleanmobile, createProjectDirectory, addUserstoMG, globalDirectorySearch, \
    search_on_name, loadcsv
from z_testing.test_config import TestConfig


class TestNewUser(TestCase):
    @pytest.mark.integration
    def test_update_tracker_with_dummydata(self):
        tconfig = TestConfig()

        assert config.getNUTrackerLocation() is not None
        testData = {'User': ['Max Rebo <maxrebo@cantana.com>'], 'Company': ['Max Rebo Band'], 'Project': ['UTC - LRI UTC'], 'Done?': ['No'], 'Action with': ['Org admin'], 'Comments': ['New user'], 'Date Started': ['30/06/2026'], 'Date Completed': ['']}
        Directory.updateTracker(config, testData)

    # Test adding to MG 'HB Confidential'
    def test_HB_Confidential(self):
        tconfig = TestConfig()
        tconfig.init_CDC()

        users_to_add = ['268849089']
        groupid = "344608816"

        statuscode, reason = addUserstoMG(groupid, users_to_add)
        assert statuscode == 200

    def test_search_global(self):
        tconfig = TestConfig()
        tconfig.init_FS1018()
        parameters = search_on_name("Tom Lythall", False)
        csvOrgAdminList = loadcsv()
        self.new_org_test(parameters, csvOrgAdminList)

    def new_org_test(self, parameters, csvOrgAdminList):
        inputs = ["Company A", "X"]  # Search for Company A, then select no matching company
        with patch("builtins.input", side_effect=inputs):
            globalDirectorySearch(parameters, csvOrgAdminList)

    @pytest.mark.integration
    def test_new_user(self, parameters, csvOrgAdminList):
        inputs = ["Henry Brothers", "0", "Y"]  # Search for HB, confirm org admins look ok
        with patch("builtins.input", side_effect=inputs):
            globalDirectorySearch(parameters, csvOrgAdminList)

class TestUI(TestCase):
    @pytest.mark.integration
    def test_open(self):
        Directory_UI.main()

    def test_press_search(self):
        app = Directory_UI.App()
        row = next(row for row in app.rows if row.id == 1)
        self.populate_row(row, "Simon Goodair", "sgoodair@csmansfield.co.uk", "", "Lincoln Stroke Unit")
        app.frame_searchclearrow.search_pressed(None)

    def populate_row(self, row, name, email, company, project):
        row.entry_usertext.set(name)
        row.entry_emailtext.set(email)
        if company: row.entry_companytext.set(company)
        if project: row.combo_project.set(project)

class TestProjectDirectory(TestCase):
    @pytest.mark.integration
    def test_createProjectDirectory(self):
        tconfig = TestConfig()
        tconfig.init_A5057()

        createProjectDirectory()


    def test_cleanmobile(self):
        assert cleanmobile("+447911123456") == "07911 123 456"
        assert cleanmobile("+44 7123 456 789") == "07123 456 789"
        assert cleanmobile("07767785321") == "07767785321"