from unittest import TestCase
from unittest.mock import patch

import pytest
from rapidfuzz import fuzz

from Setup.APIcommon import et_findtagtext, debug_element, cleanOrgName
from Setup.config import config
from a_Directory import Directory, Directory_UI
from a_Directory.Directory import cleanmobile, createProjectDirectory, addUserstoMG, globalDirectorySearch, \
    search_on_name, loadcsv, search_on_email, api_project_directory_search, open_directory_link
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

    def test_XML_parse(self):
        tconfig = TestConfig()
        tconfig.init_CLSU()
        email = "Lyndon@day-pm.com"
        parameters = search_on_email(email)
        num_users, usersXML = api_project_directory_search(parameters)  # Search for this user on the project
        assert num_users == 1
        debug_element(usersXML[0])
        assert et_findtagtext(usersXML[0], "OrganizationName") == "DAY PM"

    def test_open_directory_link(self):
        tconfig = TestConfig()
        tconfig.init_MTP()
        open_directory_link("268457782", "P+HS", "Lukasz Skatula")
        open_directory_link("268457782", "Telliing ( Finishings ) Ltd", "Danny Orwin")

    #check best fuzzy matching approach for company name variations
    def test_company_match(self):
        input_company = ["Prodeck", "M Pave", "Beresfords", "Couch Perry and Wilkes", "Telling Finishings"]
        aconex_company : list[str] = list(map(cleanOrgName,["Prodeck-Fixing Ltd", "MPave Ltd", "Beresford's Flooring Ltd", "Couch Perry & Wilkes Environmental LLP", "Telliing ( Finishings ) Ltd"]))
        ratios = []
        pratios = []
        tsortratios = []
        tsetratios = []

        for i, a in zip(input_company, aconex_company):
            ratios.append(fuzz.ratio(i, a))
            pratios.append(fuzz.partial_ratio(i, a))
            tsortratios.append(fuzz.token_sort_ratio(i, a))
            tsetratios.append(fuzz.token_set_ratio(i, a))
            print("{}, {}".format(i, a))
            print("Ratio: ", fuzz.ratio(i, a))
            print("Partial Ratio: ", fuzz.partial_ratio(i, a))
            print("Token sort ratio: ", fuzz.token_sort_ratio(i, a))
            print("Token set ratio: ", fuzz.token_set_ratio(i, a))

        scores : dict[str, float] = {
            "Ratio": sum(ratios),
            "Partial Ratio": sum(pratios),
            "Token sort ratio": sum(tsortratios),
            "Token set ratio": sum(tsetratios)
        }

        best, totalscore = max(scores.items(), key=lambda x: x[1])
        print("Best = {b} with an average score of {a}".format(b=best,a =totalscore/len(input_company)))


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

    def test_valid_row(self):
        app = Directory_UI.App()
        for row in app.rows:
            if row.id == 1:
                self.populate_row(row, "Anthony Apple", "anthony@apple.com", "Company A", "LRI Windsor")
            elif row.id == 2:
                self.populate_row(row, "Anthony Apple", "aapple@mail.com","Company A", "LRI Windsor")
            elif row.id == 3:
                self.populate_row(row, "Bob Banana", "bob@banana.com", "Company B", "Lincoln Stroke Unit")
                app.check_for_duplicates("Full Name", row)
                app.check_for_duplicates("Email Address", row)
                app.check_for_duplicates("Company Name", row)
            else:
                break


        for row in app.rows:

            row.check_if_valid()
            if row.id == 3:
                assert row.is_valid
            else:
                assert not row.is_valid

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