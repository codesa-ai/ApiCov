import sys
import os
import unittest.mock as mock
import requests

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.Coverage import LibCoverage
from modules.ExportFetcher import ExportFetcher
from modules.Utils import find_shared_libraries
from modules.logging_config import logging
from apicov import upload_coverage_data
from modules.DocGen import DocGen

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "vorbis")
SHARED_LIBS = os.path.join(os.path.dirname(__file__), "vorbis/lib/.libs")
INSTALL_DIR = os.path.join(os.path.dirname(__file__), "vorbis/include/vorbis")
APIS = [
    "vorbis_encode_ctl",
    "vorbis_encode_init",
    "vorbis_encode_init_vbr",
    "vorbis_encode_setup_init",
    "vorbis_encode_setup_managed",
]

DOCGEN_TEST_DIR = os.path.join(os.path.dirname(__file__), "test_doc")


def test_find_shared_libraries():
    logging.info("Testing find_shared_libraries in directory: %s", PROJECT_DIR)
    shared_libs = find_shared_libraries(PROJECT_DIR)
    logging.info("Found shared libraries: %s", shared_libs)
    assert len(shared_libs) > 0, "No shared libraries found"


def test_export_fetcher():
    logging.info("Testing ExportFetcher in directory: %s", PROJECT_DIR)
    lib_exports = ExportFetcher()
    for lib in os.listdir(SHARED_LIBS):
        if lib.endswith(".so"):
            lib_exports.get_exports_from_lib(os.path.join(SHARED_LIBS, lib))
    assert len(lib_exports.symbols) > 0, "No symbols found"
    lib_exports.filter_non_apis(INSTALL_DIR)
    assert len(lib_exports.apis) > 0, "No APIs found"
    assert len(lib_exports.apis) < len(lib_exports.symbols), "Filteration failed"


def test_lib_coverage():
    logging.info("Testing LibCoverage in directory: %s", PROJECT_DIR)
    lib_coverage = LibCoverage(APIS, PROJECT_DIR)
    lib_coverage.run_gcov_on_gcno_files()
    lib_coverage.populate_entry_api_cov()
    assert len(lib_coverage.api_sizes) > 0, "No API sizes found"
    assert len(lib_coverage.api_coverage) > 0, "No API coverage found"
    for api in lib_coverage.api_sizes:
        assert lib_coverage.api_sizes[api] > 0, "API size is 0"
        assert lib_coverage.api_coverage[api] < lib_coverage.api_sizes[api], (
            "API coverage is larger than API size"
        )


def test_upload_coverage_data():
    logging.info("Testing upload_coverage_data function")

    # Sample coverage data
    coverage_data = {"test_api": {"full_size": 100, "covered_lines": 50}}
    api_key = "test_api_key"

    # Mock response object
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None

    # Test successful upload
    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        result = upload_coverage_data(coverage_data, api_key)
        assert result is True, "Upload should succeed"

        # Verify the request was made with correct parameters
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://callback-373812666155.europe-west2.run.app/upload"
        assert kwargs["headers"] == {"Content-Type": "application/json"}
        assert kwargs["json"] == {"api_key": api_key, "coverage": coverage_data}

    # Test failed upload
    with mock.patch(
        "requests.post", side_effect=requests.exceptions.RequestException("Test error")
    ) as mock_post:
        result = upload_coverage_data(coverage_data, api_key)
        assert result is False, "Upload should fail"
        mock_post.assert_called_once()


def test_docgen_html():
    """
    Test DocGen HTML mode by verifying that API documentation is correctly extracted from HTML files.
    
    This test checks that:
    1. DocGen can properly convert HTML documentation files to XML
    2. The converted XML files can be parsed to extract API documentation
    3. At least one API in the test set has documentation
    
    The test uses a predefined set of HTML files in DOCGEN_TEST_DIR containing Doxygen-generated
    documentation for the Vorbis encoding APIs.
    """
    logging.info("Testing DocGen for API documentation extraction")
    docgen = DocGen(DOCGEN_TEST_DIR)
    apidoc = docgen.generate_apidoc(APIS)
    found = False
    for api in APIS:
        doc = apidoc.get(api, "")
        logging.info(f"API: {api}, Doc: {doc[:60]}{'...' if len(doc) > 60 else ''}")
        if doc.strip():
            found = True
    assert found, "No documentation found for any API in APIS"


def test_docgen_xml():
    """
    Test DocGen XML mode by verifying that API documentation is correctly extracted from XML files.
    
    This test checks that:
    1. DocGen can properly parse XML documentation files
    2. The expected API prototypes and brief descriptions are found in the extracted docs
    3. All APIs in the test set have documentation
    
    The test uses a predefined set of XML files in DOCGEN_TEST_DIR containing Doxygen-generated
    documentation for the Vorbis encoding APIs.
    """
    # Expected documentation for each API (prototype and brief)
    expected_docs = {
        'vorbis_encode_init': (
            "int vorbis_encode_init(vorbis_info *vi, long channels, long rate, long max_bitrate, long nominal_bitrate, long min_bitrate)",
            "Brief: This is the primary function within libvorbisenc for setting up managed bitrate modes."
        ),
        'vorbis_encode_setup_managed': (
            "int vorbis_encode_setup_managed(vorbis_info *vi, long channels, long rate, long max_bitrate, long nominal_bitrate, long min_bitrate)",
            "Brief: This function performs step-one of a three-step bitrate-managed encode setup."
        ),
        'vorbis_encode_init_vbr': (
            "int vorbis_encode_init_vbr(vorbis_info *vi, long channels, long rate, float base_quality)",
            "Brief: This is the primary function within libvorbisenc for setting up variable bitrate (\"quality\" based) modes."
        ),
        'vorbis_encode_setup_init': (
            "int vorbis_encode_setup_init(vorbis_info *vi)",
            "Brief: This function performs the last stage of three-step encoding setup, as described in the API overview under managed bitrate modes."
        ),
        'vorbis_encode_ctl': (
            "int vorbis_encode_ctl(vorbis_info *vi, int number, void *arg)",
            "Brief: This function implements a generic interface to miscellaneous encoder settings similar to the classic UNIX 'ioctl()' system call."
        ),
    }

    docgen = DocGen(DOCGEN_TEST_DIR, xml=True)
    apidoc = docgen.generate_apidoc(APIS)
    for api in APIS:
        doc = apidoc.get(api, "")
        logging.info(f"API: {api}, Doc: {doc[:60]}{'...' if len(doc) > 60 else ''}")
        # Check that the doc is not empty
        assert doc.strip(), f"No documentation found for API {api}"
        # Check that the doc contains the expected prototype and brief
        expected_proto, expected_brief = expected_docs[api]
        assert expected_proto in doc, f"Prototype for {api} not found in documentation.\nExpected: {expected_proto}\nActual: {doc}"
        assert expected_brief in doc, f"Brief for {api} not found in documentation.\nExpected: {expected_brief}\nActual: {doc}"


def test_docgen_init_html_mode():
    """
    Test DocGen initialization in HTML mode (should convert HTML to XML and create apicov_xml directory).
    """
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        html_file = Path(tmpdir) / "index.html"
        html_file.write_text("<html><body><h1>Test</h1></body></html>", encoding="utf-8")
        docgen = DocGen(tmpdir)
        xml_dir = Path(tmpdir) / "apicov_xml"
        assert xml_dir.exists(), "apicov_xml directory should be created"
        xml_files = list(xml_dir.glob("*.xml"))
        assert len(xml_files) > 0, "HTML file should be converted to XML"

def test_docgen_init_xml_mode():
    """
    Test DocGen initialization in XML mode (should find XML files).
    """
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_file = Path(tmpdir) / "api.xml"
        xml_file.write_text("<root></root>", encoding="utf-8")
        docgen = DocGen(tmpdir, xml=True)
        assert xml_file.as_posix() in docgen.xml_files, "XML file should be detected"

def test_docgen_generate_json_and_apidoc():
    """
    Test DocGen.generate_json and DocGen.generate_apidoc with fake API docs.
    """
    import tempfile
    import json
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        docgen = DocGen(tmpdir, xml=True)
        docgen.api_docs = {"foo": "Foo doc", "bar": "Bar doc"}
        output_file = Path(tmpdir) / "apidoc.json"
        result = docgen.generate_json(str(output_file))
        assert result is True, "generate_json should return True on success"
        assert output_file.exists(), "Output JSON file should be created"
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == docgen.api_docs, "JSON file content should match api_docs"

def test_docgen_generate_apidoc_empty():
    """
    Test DocGen.generate_apidoc with no real XML/HTML, should return empty or missing docs for unknown APIs.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        docgen = DocGen(tmpdir, xml=True)
        apis = ["notfound"]
        result = docgen.generate_apidoc(apis)
        assert isinstance(result, dict)
        assert all(api not in result or not result[api] for api in apis), "No docs should be found for missing APIs"

def test_convert_html_directory_to_xml():
    """
    Test DocGen.convert_html_directory_to_xml by converting all HTML files in DOCGEN_TEST_DIR/html
    to XML files in a temporary output directory. Checks that XML files are created and are valid.
    """
    import tempfile
    import os
    from pathlib import Path
    from bs4 import BeautifulSoup
    docgen = DocGen(DOCGEN_TEST_DIR)  # We only need the class, not the conversion in __init__
    input_dir = os.path.join(DOCGEN_TEST_DIR, "html")
    with tempfile.TemporaryDirectory() as tmp_out:
        docgen.convert_html_directory_to_xml(input_dir, tmp_out)
        # Check that for every .html/.htm file in input, a .xml file exists in output
        html_files = []
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith((".html", ".htm")):
                    rel_path = os.path.relpath(os.path.join(root, file), input_dir)
                    xml_path = os.path.splitext(os.path.join(tmp_out, rel_path))[0] + ".xml"
                    html_files.append((file, xml_path))
                    assert os.path.exists(xml_path), f"XML file not created for {file}: {xml_path}"
                    # Check that the XML file is parseable
                    with open(xml_path, "r", encoding="utf-8") as f:
                        soup = BeautifulSoup(f, "xml")
                        assert soup.find(), f"XML file {xml_path} is not valid XML or is empty"


def main():
    logging.info("Starting tests...")
    test_find_shared_libraries()
    test_export_fetcher()
    test_lib_coverage()
    test_upload_coverage_data()
    test_convert_html_directory_to_xml()
    test_docgen_html()
    test_docgen_xml()
    logging.info("All tests completed successfully")


if __name__ == "__main__":
    main()
