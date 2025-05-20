import argparse
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.Coverage import LibCoverage
from modules.ExportFetcher import ExportFetcher
from modules.Utils import find_shared_libraries
from modules.logging_config import logging 

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "vorbis")
SHARED_LIBS = os.path.join(os.path.dirname(__file__), "vorbis/lib/.libs")
INSTALL_DIR = os.path.join(os.path.dirname(__file__), "vorbis/include/vorbis")
APIS = ['vorbis_encode_ctl', 'vorbis_encode_init', 'vorbis_encode_init_vbr', 'vorbis_encode_setup_init', 'vorbis_encode_setup_managed']

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
    lib_coverage = LibCoverage(APIS, PROJECT_DIR)
    lib_coverage.run_gcov_on_gcno_files()
    lib_coverage.populate_entry_api_cov()
    assert len(lib_coverage.api_sizes) > 0, "No API sizes found"
    assert len(lib_coverage.api_coverage) > 0, "No API coverage found"
    for api in lib_coverage.api_sizes:
        assert lib_coverage.api_sizes[api] > 0, "API size is 0"
        assert lib_coverage.api_coverage[api] < lib_coverage.api_sizes[api], "API coverage is larger than API size"

def main():
    logging.info("Starting tests...")
    test_find_shared_libraries()
    test_export_fetcher()
    test_lib_coverage()
    logging.info("All tests completed successfully")

if __name__ == "__main__":
    main()