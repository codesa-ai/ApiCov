import argparse
import json
import os
import requests
import bs4
import lxml
import zipfile

from modules.ExportFetcher import ExportFetcher
from modules.Utils import find_shared_libraries, compress_gcov_files
from modules.Coverage import LibCoverage
from modules.logging_config import logging
from modules.DocGen import DocGen



def upload_coverage_data(coverage_data, api_key):
    """Upload coverage data to the endpoint."""
    url = "https://callback-373812666155.europe-west2.run.app/upload"
    headers = {"Content-Type": "application/json"}
    payload = {"api_key": api_key, "coverage": coverage_data}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info("Successfully uploaded coverage data")
        return True
    except requests.exceptions.RequestException as e:
        logging.error("Failed to upload coverage data: %s", e)
        return False


def create_gcov_archive(coverage_instance, output_path=None, archive_name="gcov_files.zip"):
    """
    Create a compressed zip archive of all collected .gcov files for upload.
    
    This function uses the Utils.compress_gcov_files function to create a zip
    archive containing all the .gcov files that were generated during
    coverage analysis. The archive can be uploaded to a server for
    further processing or storage.
    
    Args:
        coverage_instance (LibCoverage): LibCoverage instance containing gcov_files
        output_path (str, optional): Directory where the zip file should be created.
                                    If None, uses a temporary directory.
        archive_name (str, optional): Name of the zip archive file. 
                                    Defaults to "gcov_files.zip".
    
    Returns:
        str: Path to the created zip archive file, or None if no .gcov files exist
        
    Raises:
        FileNotFoundError: If any of the .gcov files don't exist
        OSError: If there are issues creating the zip file
    """
    if not coverage_instance.gcov_files:
        logging.warning("No .gcov files available for archiving. Run run_gcov_on_gcno_files() first.")
        return None
    
    logging.info(f"Creating gcov archive with {len(coverage_instance.gcov_files)} files")
    return compress_gcov_files(coverage_instance.gcov_files, output_path, archive_name)


def main():
    parser = argparse.ArgumentParser(description="Code SA API Coverage Tool")
    parser.add_argument("project_dir", type=str, help="Path to the root directory")
    parser.add_argument("api_key", type=str, help="API key for uploading coverage data")
    parser.add_argument(
        "--install_dir",
        type=str,
        required=True,
        help="Path to where the exported header files are installed",
    )
    parser.add_argument(
        "--doxygen_path",
        type=str,
        default=None,
        help="Path to the Doxygen HTML files (optional)",
    )

    args = parser.parse_args()

    logging.debug("Looking for shared libraries in the project directory")
    project_dir = os.path.abspath(os.path.expanduser(args.project_dir))
    shared_libs = find_shared_libraries(project_dir)

    logging.info("Shared libraries found: %s", shared_libs)

    logging.debug("Identifying exports from shared libraries")
    lib_exports = ExportFetcher()
    for lib in shared_libs:
        lib_exports.get_exports_from_lib(lib)

    logging.info("Total number of symbols found: %d", len(lib_exports.symbols))

    logging.info("Filtering non-API exports")
    install_dir = os.path.abspath(os.path.expanduser(args.install_dir))
    lib_exports.filter_non_apis(install_dir)

    logging.info("Total number of APIs found: %d", len(lib_exports.apis))
    json_data = {"apis": lib_exports.apis}
    api_file = os.path.join(project_dir, "apis.json")
    logging.debug("Writing APIs to:  %s", api_file)
    with open(api_file, "w") as fh:
        json.dump(json_data, fh)

    entry_cov = LibCoverage(lib_exports.apis, project_dir)
    logging.info("Running gcov to identify API sizes and coverage")
    entry_cov.run_gcov_on_gcno_files()
    logging.info("Populate API sizes and coverage")
    entry_cov.populate_entry_api_cov()


    if args.doxygen_path:
        logging.info("Generating API documentation")
        doxygen_path = os.path.abspath(os.path.expanduser(args.doxygen_path))
        doc_gen = DocGen(doxygen_path, xml=True)
        apidoc = doc_gen.generate_apidoc(lib_exports.apis)
    else:
        logging.info("No Doxygen path provided, skipping API documentation generation")
        apidoc = None

    json_data = {}
    no_cov_apis = []
    no_doc_apis = []
    for api in lib_exports.apis:

        if api in entry_cov.api_sizes:
            json_data[api] = {}
            json_data[api]["full_size"] = entry_cov.api_sizes[api]
            json_data[api]["covered_lines"] = entry_cov.api_coverage[api]
        else:
            logging.error("Failed to find size for API: %s", api)
            no_cov_apis.append(api)
        
        if apidoc and api in apidoc:
            json_data[api]["apidoc"] = apidoc[api]
        else:
            logging.error("Failed to find documentation for API: %s", api)
            no_doc_apis.append(api)


    apicov_file = os.path.join(args.project_dir, "api_coverage.json")
    logging.info("Writing API data to: %s", apicov_file)
    with open(apicov_file, "w") as fh:
        json.dump(json_data, fh)

    if no_cov_apis:
        logging.error("Failed to find size for %d APIs: %s", len(no_cov_apis), no_cov_apis)

    if no_doc_apis:
        logging.error("Failed to find documentation for %d APIs: %s", len(no_doc_apis), no_doc_apis)

    # Create gcov archive for upload
    logging.info("Creating gcov archive for upload")
    archive_path = create_gcov_archive(entry_cov)
    if archive_path:
        logging.info(f"Gcov archive created successfully: {archive_path}")
    else:
        logging.warning("Failed to create gcov archive")

    # Upload coverage data if API key is provided
    if args.api_key:
        logging.info("Uploading data to endpoint")
        upload_coverage_data(json_data, args.api_key)


if __name__ == "__main__":
    main()
