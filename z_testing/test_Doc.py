from unittest import TestCase

import pytest

from Setup.APIcommon import et_findtagtext
from Setup.config import config
from Setup.Doc import getDocumentLink, searchForDoc, create_doc_xml
from z_testing.test_config import TestConfig
from xml.etree.ElementTree import Element


class TestDoc(TestCase):
    @pytest.mark.integration
    def test_get_document_link(self):
        tconfig = TestConfig()
        tconfig.init_WPS()

        getDocumentLink(config, "1348828088504028609")

    def test_docfields(self):
        tconfig = TestConfig()
        tconfig.init_CMUH()
        config.docfields()

        assert config.docfields() is not None and not []
        assert config.return_doc_fields() is not None and not []
        assert config.mandatory_doc_fields() is not None and not []

        docfieldnames = [df.label() for df in config.docfields()]

        mandatorydocfieldnames = [df.label() for df in config.mandatory_doc_fields()]
        searchabledocfieldnames = [df.label() for df in config.return_doc_fields()]
        assert "Revision" in docfieldnames
        assert "Revision" in mandatorydocfieldnames
        assert "Revision" in searchabledocfieldnames
        assert "Created By" in mandatorydocfieldnames
        assert "Created By" in searchabledocfieldnames
        assert "Tracking ID" in searchabledocfieldnames
        assert "Tracking ID" not in [df.label() for df in config.required_return_doc_fields()]

    def test_searchfordoc(self):
        tconfig = TestConfig()
        tconfig.init_CMUH()
        self.test_docfields()
        returnfields = ",".join([df.search_field() for df in config.required_return_doc_fields()]) + ",trackingid"
        print(returnfields)
        docxml = searchForDoc(config, "docno:{}".format(config.project().getWFTrackerNumber()), returnfields)
        assert docxml is not None

        et_findtagtext(docxml, "Author")
        et_findtagtext(docxml, "DocumentStatus")
        return docxml

    @pytest.mark.integration
    def test_createdocxml(self):
        docxml = self.test_searchfordoc()
        _, _, xmldata = create_doc_xml(config, "2000/01/01", docxml, config.project().getWFExportDataLocation())
        assert "SelectList3" in xmldata

    def test_mandatory_doc_fields(self):
        tconfig = TestConfig()
        tconfig.init_9910()
        dfields = config.mandatory_doc_fields()
        [print(df.identifier()) for df in dfields]

        assert config.searchForFormField("Select List 3") is not None

    def test_doc_statuses(self):
        tconfig = TestConfig()
        tconfig.init_9910()

        dstatuses = config.docStatuses()
        assert "S2 - Suitable for Information" in dstatuses.keys()


    def test_doctypes(self):
        tconfig = TestConfig()
        tconfig.init_CMUH()

        assert "Drawing" in config.docTypes().keys()

    def test_search_for_formfield(self):
        tconfig = TestConfig()
        tconfig.init_JFW()

        assert config.searchForFormField('Milestone Date')
