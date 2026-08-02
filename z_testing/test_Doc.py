from unittest import TestCase

import pytest

from Setup.config import config
from Setup.Doc import getDocumentLink
from z_testing.test_config import TestConfig


class TestDoc(TestCase):
    @pytest.mark.integration
    def test_get_document_link(self):
        tconfig = TestConfig()
        tconfig.init_WPS()

        getDocumentLink(config, "1348828088504028609")

    def test_mandatory_doc_fields(self):
        tconfig = TestConfig()
        tconfig.init_9910()
        dfields = config.mandatorydocfields()
        [print(df.identifier()) for df in dfields]

        assert config.searchForFormField("Select List 3") is not None

    def test_doc_statuses(self):
        tconfig = TestConfig()
        tconfig.init_9910()

        dstatuses = config.docStatuses()

        print(dstatuses["S2 - Suitable for Information"])
        print(dstatuses)

    #TODO why can't it find this??
    @pytest.mark.skip
    def test_search_for_formfield(self):
        tconfig = TestConfig()
        tconfig.init_JFW()

        assert config.searchForFormField('milestonedate')
