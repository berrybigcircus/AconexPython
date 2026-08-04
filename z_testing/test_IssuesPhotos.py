from unittest import TestCase

import pytest

from Setup.config import config
from c_Field.IssuesPhotos import loadRoomCoords, check_coordinates, loadPhotos
from z_testing.test_config import TestConfig


class TestIssues(TestCase):
    @pytest.mark.integration
    def test_geotagger(self):
        tconfig = TestConfig()
        tconfig.init_ea()
        room_polygons, room_heights = loadRoomCoords(config)
        assert check_coordinates(room_polygons, room_heights, "52; 54; 18.379", "1; 14; 20.937", "84") is True
        assert check_coordinates(room_polygons, room_heights, "55; 54; 18.379", "1; 14; 20.937", "84") is False

    @pytest.mark.integration
    def test_coordinates(self):
        tconfig = TestConfig()
        tconfig.init_ea()
        room_polygons, room_heights = loadRoomCoords(config)
        assert check_coordinates(room_polygons, room_heights, "52; 54; 18.379", "1; 14; 20.937", "84") is True
        assert check_coordinates(room_polygons, room_heights, "55; 54; 18.379", "1; 14; 20.937", "84") is False

    @pytest.mark.integration
    def test_loadphotos(self):
        tconfig = TestConfig()
        tconfig.init_ea()
        folderpath = "C:\\Users\\nicole.millinship\\PycharmProjects\\AconexPython\\c_Field\\GeotaggedPhotos\\HBC Office"
        loadPhotos(folderpath)