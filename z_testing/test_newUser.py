from unittest import TestCase

from Setup.config import config
from a_NewUser import newUser
from a_NewUser.newUser import cleanmobile, createProjectDirectory
from z_testing.test_config import TestConfig


class TestNewUser(TestCase):
    def test_update_tracker_with_dummydata(self):
        tconfig = TestConfig()

        assert config.getNUTrackerLocation() is not None
        testData = {'User': ['Gayathri Saudha <Gayathri.Saudha@curtins.com>'], 'Company': ['Curtins Consulting'], 'Project': ['UTC - LRI UTC'], 'Done?': ['No'], 'Action with': ['Org admin'], 'Comments': ['New user'], 'Date Started': ['30/06/2026'], 'Date Completed': ['']}
        newUser.updateTracker(config, testData)

    def test_newUser_for_chosen_project(self):
        tconfig = TestConfig()
        tconfig.init_UTC()

        newUser.main()



class TestProjectDirectory(TestCase):

    def test_createProjectDirectory(self):
        tconfig = TestConfig()
        tconfig.init_A5057()

        createProjectDirectory()


    def test_cleanmobile(self):
        assert cleanmobile("+447911123456") == "07911 123 456"
        assert cleanmobile("+44 7123 456 789") == "07123 456 789"
        assert cleanmobile("07767785321") == "07767785321"