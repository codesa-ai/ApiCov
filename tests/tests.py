import sys
import os
import unittest.mock as mock
import requests
import json
import tempfile
import shutil
import tarfile

from pathlib import Path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.Coverage import LibCoverage  # noqa: E402
from modules.ExportFetcher import ExportFetcher  # noqa: E402
from modules.Utils import find_shared_libraries  # noqa: E402
from modules.Utils import find_header_files  # noqa: E402
from modules.Utils import compress_lcov_file  # noqa: E402
from apicov import generate_lcov_info  # noqa: E402
from modules.logging_config import logging  # noqa: E402
from apicov import upload_data  # noqa: E402
from modules.DocGen import DocGen  # noqa: E402

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


def test_upload_data():
    logging.info("Testing upload_data function")

    # Sample coverage data
    coverage_data = {"test_file.h": {"test_api": {"full_size": 100, "covered_lines": 50}}}
    api_key = "test_api_key"
    header_files = ["test_file.h"]

    # Mock response object
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None

    # Test successful upload
    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        result = upload_data(coverage_data, header_files, api_key)
        assert result is True, "Upload should succeed"

        # Verify the request was made with correct parameters
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://callback-373812666155.europe-west2.run.app"
        assert "data" in kwargs
        assert kwargs["data"]["api_key"] == api_key
        assert json.loads(kwargs["data"]["coverage"]) == coverage_data

    # Test failed upload
    with mock.patch(
        "requests.post", side_effect=requests.exceptions.RequestException("Test error")
    ) as mock_post:
        result = upload_data(coverage_data, header_files, api_key)
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
        "vorbis_encode_init": (
            "int vorbis_encode_init(vorbis_info *vi, long channels, long rate, long max_bitrate, long nominal_bitrate, long min_bitrate)",
            "Brief: This is the primary function within libvorbisenc for setting up managed bitrate modes.",
        ),
        "vorbis_encode_setup_managed": (
            "int vorbis_encode_setup_managed(vorbis_info *vi, long channels, long rate, long max_bitrate, long nominal_bitrate, long min_bitrate)",
            "Brief: This function performs step-one of a three-step bitrate-managed encode setup.",
        ),
        "vorbis_encode_init_vbr": (
            "int vorbis_encode_init_vbr(vorbis_info *vi, long channels, long rate, float base_quality)",
            'Brief: This is the primary function within libvorbisenc for setting up variable bitrate ("quality" based) modes.',
        ),
        "vorbis_encode_setup_init": (
            "int vorbis_encode_setup_init(vorbis_info *vi)",
            "Brief: This function performs the last stage of three-step encoding setup, as described in the API overview under managed bitrate modes.",
        ),
        "vorbis_encode_ctl": (
            "int vorbis_encode_ctl(vorbis_info *vi, int number, void *arg)",
            "Brief: This function implements a generic interface to miscellaneous encoder settings similar to the classic UNIX 'ioctl()' system call.",
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
        assert expected_proto in doc, (
            f"Prototype for {api} not found in documentation.\nExpected: {expected_proto}\nActual: {doc}"
        )
        assert expected_brief in doc, (
            f"Brief for {api} not found in documentation.\nExpected: {expected_brief}\nActual: {doc}"
        )


def test_docgen_init_html_mode():
    """
    Test DocGen initialization in HTML mode (should convert HTML to XML and create apicov_xml directory).
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        html_file = Path(tmpdir) / "index.html"
        html_file.write_text(
            "<html><body><h1>Test</h1></body></html>", encoding="utf-8"
        )
        DocGen(tmpdir)
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
        assert all(api not in result or not result[api] for api in apis), (
            "No docs should be found for missing APIs"
        )


def test_convert_html_directory_to_xml():
    """
    Test DocGen.convert_html_directory_to_xml by converting all HTML files in DOCGEN_TEST_DIR/html
    to XML files in a temporary output directory. Checks that XML files are created and are valid.
    """
    import tempfile
    import os
    from bs4 import BeautifulSoup

    docgen = DocGen(
        DOCGEN_TEST_DIR
    )  # We only need the class, not the conversion in __init__
    input_dir = os.path.join(DOCGEN_TEST_DIR, "html")
    with tempfile.TemporaryDirectory() as tmp_out:
        docgen.convert_html_directory_to_xml(input_dir, tmp_out)
        # Check that for every .html/.htm file in input, a .xml file exists in output
        html_files = []
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith((".html", ".htm")):
                    rel_path = os.path.relpath(os.path.join(root, file), input_dir)
                    xml_path = (
                        os.path.splitext(os.path.join(tmp_out, rel_path))[0] + ".xml"
                    )
                    html_files.append((file, xml_path))
                    assert os.path.exists(xml_path), (
                        f"XML file not created for {file}: {xml_path}"
                    )
                    # Check that the XML file is parseable
                    with open(xml_path, "r", encoding="utf-8") as f:
                        soup = BeautifulSoup(f, "xml")
                        assert soup.find(), (
                            f"XML file {xml_path} is not valid XML or is empty"
                        )


def test_generate_lcov_info():
    """
    Test generate_lcov_info function that runs lcov to generate coverage info files.

    This test checks that:
    1. lcov command is available on the system
    2. lcov can successfully process gcno/gcda files in the vorbis test directory
    3. An .info file is generated with coverage data
    """

    logging.info("Testing generate_lcov_info with vorbis project")

    # Check if lcov is available
    if not shutil.which("lcov"):
        logging.warning("lcov not installed, skipping test")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, "coverage.info")
        result = generate_lcov_info(PROJECT_DIR, output_file)

        assert result is True, "generate_lcov_info should return True on success"
        assert os.path.exists(output_file), "Coverage info file should be created"

        # Check that the file has content
        file_size = os.path.getsize(output_file)
        logging.info(f"Generated lcov info file size: {file_size} bytes")
        assert file_size > 0, "Coverage info file should not be empty"

        # Check file contains expected lcov format markers
        with open(output_file, "r") as f:
            content = f.read()
            assert "SF:" in content or "TN:" in content, (
                "Coverage info file should contain lcov format markers"
            )


def test_compress_lcov_file():
    """
    Test compress_lcov_file function that compresses .info files into tar archives.

    This test checks that:
    1. A valid .info file is compressed into a tar.xz archive
    2. The archive is created with the correct name
    3. The archive contains the original file
    4. Both .tar.xz and .tgz formats work correctly
    5. Missing files are handled gracefully
    """

    logging.info("Testing compress_lcov_file function")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake .info file with lcov-like content
        info_file = os.path.join(tmpdir, "test.info")
        with open(info_file, "w") as f:
            f.write("TN:\n")
            f.write("SF:/path/to/source.c\n")
            f.write("FN:10,test_function\n")
            f.write("DA:10,1\n")
            f.write("DA:11,1\n")
            f.write("DA:12,0\n")
            f.write("LF:3\n")
            f.write("LH:2\n")
            f.write("end_of_record\n")

        # Test .tar.xz compression
        output_dir = os.path.join(tmpdir, "output_xz")
        os.makedirs(output_dir)
        archive_path = compress_lcov_file(info_file, output_dir, "coverage.tar.xz")

        assert archive_path is not None, "compress_lcov_file should return archive path"
        assert os.path.exists(archive_path), "Archive file should exist"
        assert archive_path.endswith(".tar.xz"), "Archive should have .tar.xz extension"

        # Verify archive contents
        with tarfile.open(archive_path, "r:xz") as tar:
            names = tar.getnames()
            assert "test.info" in names, "Archive should contain the info file"

        # Test .tgz compression
        output_dir_gz = os.path.join(tmpdir, "output_gz")
        os.makedirs(output_dir_gz)
        archive_path_gz = compress_lcov_file(info_file, output_dir_gz, "coverage.tgz")

        assert archive_path_gz is not None, "compress_lcov_file should return archive path for tgz"
        assert os.path.exists(archive_path_gz), "Gzip archive file should exist"

        # Verify gzip archive contents
        with tarfile.open(archive_path_gz, "r:gz") as tar:
            names = tar.getnames()
            assert "test.info" in names, "Gzip archive should contain the info file"

        # Test with non-existent file
        result = compress_lcov_file("/nonexistent/file.info", tmpdir)
        assert result is None, "compress_lcov_file should return None for missing file"


def test_find_header_files():
    """
    Test find_header_files function to verify it correctly finds C/C++ header files.

    This test checks that:
    1. Header files are found in the test directory
    2. The returned paths are relative to the root directory
    3. Common header extensions are properly detected
    4. Hidden directories are included in the search
    """

    logging.info("Testing find_header_files in directory: %s", INSTALL_DIR)

    # Test with the vorbis include directory
    headers = find_header_files(INSTALL_DIR)
    logging.info("Found %d header files", len(headers))

    # Check that we found some headers
    assert len(headers) > 0, "No header files found in vorbis include directory"

    # Check that paths are relative (not starting with the root dir)
    for header in headers:
        assert not header.startswith(INSTALL_DIR), (
            f"Header path should be relative: {header}"
        )
        # Check that it's actually a header file
        assert any(
            header.lower().endswith(ext)
            for ext in [
                ".h",
                ".hpp",
                ".hxx",
                ".h++",
                ".hh",
                ".tpp",
                ".ipp",
                ".inl",
                ".inc",
            ]
        ), f"File {header} doesn't have a valid header extension"

    # Log some of the found headers for debugging
    for header in headers[:5]:  # Show first 5 headers
        logging.info("  Found header: %s", header)

    # Test with the whole project directory (should find more headers)
    all_headers = find_header_files(PROJECT_DIR)
    logging.info("Found %d header files in entire project", len(all_headers))

    # Should find at least the vorbis headers we found earlier
    assert len(all_headers) >= len(headers), (
        "Project directory should contain at least as many headers as include directory"
    )


def test_apis_json_structure():
    """
    Test that apis.json has the correct dict-of-dicts structure.

    The expected structure is:
    {
        "apis": {
            "header_file.h": ["api1", "api2", ...],
            ...
        }
    }

    Where the outer dict has an "apis" key containing a dict mapping
    header file names to lists of API function names.
    """
    logging.info("Testing apis.json structure")

    # Use ExportFetcher to generate the apis structure
    lib_exports = ExportFetcher()
    for lib in os.listdir(SHARED_LIBS):
        if lib.endswith(".so"):
            lib_exports.get_exports_from_lib(os.path.join(SHARED_LIBS, lib))
    lib_exports.filter_non_apis(INSTALL_DIR)

    # Verify the structure is a dict of lists (header -> [apis])
    assert isinstance(lib_exports.apis, dict), "apis should be a dict"
    assert len(lib_exports.apis) > 0, "apis should not be empty"

    for header_file, apis_list in lib_exports.apis.items():
        assert isinstance(header_file, str), f"Header key should be a string, got {type(header_file)}"
        assert isinstance(apis_list, list), f"APIs for {header_file} should be a list, got {type(apis_list)}"
        assert len(apis_list) > 0, f"APIs list for {header_file} should not be empty"
        for api in apis_list:
            assert isinstance(api, str), f"API name should be a string, got {type(api)}"

    # Create the JSON structure as apicov.py does
    json_data = {"apis": lib_exports.apis}

    # Verify it can be serialized and deserialized correctly
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(json_data, f)
        temp_path = f.name

    try:
        with open(temp_path, "r") as f:
            loaded_data = json.load(f)

        assert "apis" in loaded_data, "JSON should have 'apis' key"
        assert isinstance(loaded_data["apis"], dict), "apis should be a dict"

        for header_file, apis_list in loaded_data["apis"].items():
            assert isinstance(apis_list, list), f"APIs for {header_file} should be a list after JSON round-trip"

        logging.info(f"apis.json structure valid: {len(loaded_data['apis'])} header files")
    finally:
        os.unlink(temp_path)


def test_api_coverage_json_structure():
    """
    Test that api_coverage.json has the correct dict-of-dicts structure.

    The expected structure is:
    {
        "header_file.h": {
            "api_name": {
                "full_size": int,
                "covered_lines": int,
                "apidoc": str (optional)
            },
            ...
        },
        ...
    }

    Where the outer dict maps header file names to dicts of API coverage data.
    """
    logging.info("Testing api_coverage.json structure")

    # Use ExportFetcher to get APIs
    lib_exports = ExportFetcher()
    for lib in os.listdir(SHARED_LIBS):
        if lib.endswith(".so"):
            lib_exports.get_exports_from_lib(os.path.join(SHARED_LIBS, lib))
    lib_exports.filter_non_apis(INSTALL_DIR)

    # Get coverage data
    all_apis = []
    for file, apis in lib_exports.apis.items():
        for api in apis:
            all_apis.append(api)

    lib_coverage = LibCoverage(all_apis, PROJECT_DIR)
    lib_coverage.run_gcov_on_gcno_files()
    lib_coverage.populate_entry_api_cov()

    # Build the api_coverage structure as apicov.py does
    json_data = {}
    for file, apis in lib_exports.apis.items():
        json_data[file] = {}
        for api in apis:
            json_data[file][api] = {
                "full_size": 0,
                "covered_lines": 0
            }
            if api in lib_coverage.api_sizes:
                json_data[file][api]["full_size"] = lib_coverage.api_sizes[api]
                json_data[file][api]["covered_lines"] = lib_coverage.api_coverage[api]

    # Verify structure
    assert isinstance(json_data, dict), "api_coverage should be a dict"
    assert len(json_data) > 0, "api_coverage should not be empty"

    for header_file, apis_dict in json_data.items():
        assert isinstance(header_file, str), f"Header key should be a string, got {type(header_file)}"
        assert isinstance(apis_dict, dict), f"APIs for {header_file} should be a dict, got {type(apis_dict)}"

        for api_name, coverage_data in apis_dict.items():
            assert isinstance(api_name, str), f"API name should be a string, got {type(api_name)}"
            assert isinstance(coverage_data, dict), f"Coverage data for {api_name} should be a dict"
            assert "full_size" in coverage_data, f"Coverage data for {api_name} should have 'full_size'"
            assert "covered_lines" in coverage_data, f"Coverage data for {api_name} should have 'covered_lines'"
            assert isinstance(coverage_data["full_size"], (int, float)), f"full_size should be numeric"
            assert isinstance(coverage_data["covered_lines"], (int, float)), f"covered_lines should be numeric"

    # Verify JSON serialization round-trip
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(json_data, f)
        temp_path = f.name

    try:
        with open(temp_path, "r") as f:
            loaded_data = json.load(f)

        assert isinstance(loaded_data, dict), "Loaded data should be a dict"

        for header_file, apis_dict in loaded_data.items():
            assert isinstance(apis_dict, dict), f"APIs for {header_file} should be a dict after JSON round-trip"
            for api_name, coverage_data in apis_dict.items():
                assert isinstance(coverage_data, dict), f"Coverage data should be a dict after JSON round-trip"

        total_apis = sum(len(apis) for apis in loaded_data.values())
        logging.info(f"api_coverage.json structure valid: {len(loaded_data)} header files, {total_apis} total APIs")
    finally:
        os.unlink(temp_path)


def main():
    logging.info("Starting tests...")
    test_find_shared_libraries()
    test_find_header_files()
    test_export_fetcher()
    test_lib_coverage()
    test_upload_data()
    test_convert_html_directory_to_xml()
    test_docgen_html()
    test_docgen_xml()
    test_generate_lcov_info()
    test_compress_lcov_file()
    test_apis_json_structure()
    test_api_coverage_json_structure()
    logging.info("All tests completed successfully")


if __name__ == "__main__":
    main()
