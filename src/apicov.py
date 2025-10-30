import argparse
import json
import os
import requests

from modules.ExportFetcher import ExportFetcher
from modules.Utils import find_shared_libraries, compress_gcov_files, find_header_files
from modules.Coverage import LibCoverage
from modules.logging_config import logging
from modules.DocGen import DocGen
import sys


def upload_data(coverage_data: dict, headers_data: dict, api_key: str, archive_path: str | None = None):
    """Upload coverage data to the endpoint using multipart/form-data."""
    url = "https://callback-373812666155.europe-west2.run.app"
    # Prepare multipart form data
    files = {}
    data = {
        "api_key": api_key,
        "coverage": json.dumps(coverage_data),
        "headers": json.dumps(headers_data)
    }
    if archive_path:
        # Determine content type based on file extension
        if archive_path.endswith(".tar.xz") or archive_path.endswith(".txz"):
            content_type = "application/x-xz"
        elif archive_path.endswith(".tgz") or archive_path.endswith(".tar.gz"):
            content_type = "application/gzip"
        else:
            content_type = "application/octet-stream"

        files["coverage_files"] = (
            os.path.basename(archive_path),
            open(archive_path, "rb"),
            content_type,
        )
        try:
            response = requests.post(url, data=data, files=files)
            response.raise_for_status()
            logging.info("Successfully uploaded coverage data")
            return True
        except requests.exceptions.RequestException as e:
            logging.error("Failed to upload coverage data: %s", e)
            return False
        finally:
            files["coverage_files"][1].close()
    else:
        try:
            response = requests.post(url, data=data, files=None)
            response.raise_for_status()
            logging.info("Successfully uploaded coverage data")
            return True
        except requests.exceptions.RequestException as e:
            logging.error("Failed to upload coverage data: %s", e)
            return False


def create_gcov_archive(
    coverage_instance: LibCoverage,
    output_path: str | None = None,
    archive_name: str = "coverage_data.tar.xz",
) -> str | None:
    """
    Create a compressed .tar.xz archive of all collected .gcov files for upload.

    This function uses the Utils.compress_gcov_files function to create a .tar.xz
    archive containing all the .gcov files that were generated during
    coverage analysis. The archive can be uploaded to a server for
    further processing or storage.

    Args:
        coverage_instance (LibCoverage): LibCoverage instance containing gcov_files
        output_path (str, optional): Directory where the archive file should be created.
                                    If None, uses a temporary directory.
        archive_name (str, optional): Name of the archive file.
                                    Defaults to "coverage_data.tar.xz".

    Returns:
        str: Path to the created archive file, or None if no .gcov files exist

    Raises:
        FileNotFoundError: If any of the .gcov files don't exist
        OSError: If there are issues creating the archive file
    """
    if not coverage_instance.gcov_files:
        logging.warning(
            "No .gcov files available for archiving. Run run_gcov_on_gcno_files() first."
        )
        return None

    logging.info(
        f"Creating gcov archive with {len(coverage_instance.gcov_files)} files"
    )
    return compress_gcov_files(
        coverage_instance.gcov_files,
        output_path,
        archive_name,
        coverage_instance._root_dir,
    )


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
    parser.add_argument(
        "--xml",
        dest="xml",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use XML mode for DocGen (default: True)",
    )

    args = parser.parse_args()

    # Validate project_dir exists
    project_dir = os.path.abspath(os.path.expanduser(args.project_dir))
    if not os.path.isdir(project_dir):
        logging.error(f"Error: project_dir does not exist: {args.project_dir}")
        sys.exit(1)

    # Validate api_key is not empty
    if not args.api_key or args.api_key.strip() == "":
        logging.error("Error: api_key is required but not provided")
        sys.exit(1)

    # Validate install_dir exists
    install_dir = os.path.abspath(os.path.expanduser(args.install_dir))
    if not os.path.isdir(install_dir):
        logging.error(f"Error: install_dir does not exist: {args.install_dir}")
        sys.exit(1)

    # Validate doxygen_path if provided
    if args.doxygen_path:
        doxygen_path = os.path.abspath(os.path.expanduser(args.doxygen_path))
        if not os.path.isdir(doxygen_path):
            logging.error(f"Error: doxygen_path does not exist: {args.doxygen_path}")
            sys.exit(1)

    logging.info(f"Looking for shared libraries in the install directory: {install_dir}")

    # Check if include directory exists within install_dir
    include_dir = os.path.join(install_dir, 'include')
    if os.path.isdir(include_dir):
        header_search_dir = include_dir
        logging.info(f"Found include directory, searching for headers in: {include_dir}")
    else:
        header_search_dir = install_dir
        logging.info(f"No include directory found, searching for headers in: {install_dir}")

    header_files = find_header_files(header_search_dir)
    logging.info("Header files found: %s", header_files)

    # Save header files to JSON
    headers_file = os.path.join(project_dir, "headers.json")
    logging.debug("Writing header files to: %s", headers_file)
    headers_data = {"headers": header_files, "count": len(header_files)}
    with open(headers_file, "w") as fh:
        json.dump(headers_data, fh, indent=2)

    shared_libs = find_shared_libraries(install_dir)

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
        doc_gen = DocGen(doxygen_path, xml=args.xml)
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
        logging.error(
            "Failed to find size for %d APIs: %s", len(no_cov_apis), no_cov_apis
        )

    if no_doc_apis:
        logging.error(
            "Failed to find documentation for %d APIs: %s",
            len(no_doc_apis),
            no_doc_apis,
        )

    # Create gcov archive for upload
    logging.info("Creating gcov archive for upload")
    archive_path = create_gcov_archive(entry_cov, archive_name="coverage_data.tar.xz")
    if archive_path:
        logging.info(f"Gcov archive created successfully: {archive_path}")
    else:
        logging.warning("Failed to create gcov archive")

    # Upload coverage data if API key is provided
    if args.api_key:
        logging.info("Uploading data to endpoint")
        upload_data(json_data, headers_data, args.api_key, archive_path)


if __name__ == "__main__":
    main()
