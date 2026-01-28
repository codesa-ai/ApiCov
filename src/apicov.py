import argparse
import json
import os
import requests
import subprocess
import tarfile

from modules.ExportFetcher import ExportFetcher
from modules.Utils import (
    find_shared_libraries,
    find_header_files,
    compress_lcov_file,
    identify_build_system,
    extract_linking_flags,
)
from modules.Coverage import LibCoverage
from modules.logging_config import logging
from modules.DocGen import DocGen
import sys

UPLOAD_URL = "https://callback-373812666155.europe-west2.run.app"

def upload_data(
    coverage_data: dict,
    header_files: list,
    linking_flags: str,
    api_key: str,
    archive_path: str | None = None,
):
    """Upload coverage data to the endpoint using multipart/form-data."""
    # Prepare multipart form data
    data = {
        "api_key": api_key,
        "coverage": json.dumps(coverage_data),
        "headers": json.dumps(header_files),
        "linking_flags": linking_flags,
    }
    logging.debug(f"DEBUG: Uploading data to {UPLOAD_URL}")
    logging.debug(f"DEBUG: Data: {data}")
    logging.debug(f"DEBUG: Archive path: {archive_path}")
    if archive_path:
        # Determine content type based on file extension
        if archive_path.endswith(".tar.xz") or archive_path.endswith(".txz"):
            logging.debug("DEBUG: Content type: application/x-xz")
            content_type = "application/x-xz"
        elif archive_path.endswith(".tgz") or archive_path.endswith(".tar.gz"):
            logging.debug("DEBUG: Content type: application/gzip")
            content_type = "application/gzip"
        else:
            logging.debug("DEBUG: Content type: application/octet-stream")
            content_type = "application/octet-stream"

        files = {"coverage_files": (os.path.basename(archive_path), open(archive_path, "rb"), content_type)}
        try:
            logging.info("Attempting to upload coverage data")
            response = requests.post(UPLOAD_URL, data=data, files=files)
            response.raise_for_status()
            logging.info("Successfully uploaded coverage data")
            return True
        except requests.exceptions.RequestException as e:
            logging.error("ERROR: Failed to upload coverage data: %s", e)
            return False
        finally:
            files["coverage_files"][1].close()
    else:
        try:
            logging.debug("DEBUG: Uploading empty files")
            response = requests.post(UPLOAD_URL, data=data, files={})
            response.raise_for_status()
            logging.debug("DEBUG: Successfully uploaded coverage data")
            return True
        except requests.exceptions.RequestException as e:
            logging.error("ERROR: Failed to upload coverage data: %s", e)
            return False


def generate_lcov_info(library_dir: str, output_file: str) -> bool:
    """
    Generate lcov coverage info file using lcov command.

    Args:
        library_dir (str): Root path of the location of the library
        output_file (str): Path to the output .info file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        cmd = [
            "lcov",
            "--rc",
            "branch_coverage=1",
            "--ignore-errors",
            "mismatch,gcov,source",
            "-c",
            "--directory",
            library_dir,
            "--output-file",
            output_file,
        ]
        logging.info(f"Running lcov command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stderr:
            logging.debug(f"DEBUG: lcov stderr: {result.stderr}")
        logging.info(f"Successfully generated lcov info file: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"ERROR: Failed to run lcov: {e}")
        logging.error(f"ERROR: lcov stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error("ERROR: lcov command not found. Please ensure lcov is installed.")
        return False


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
    parser.add_argument(
        "--compile",
        type=str,
        default=None,
        help="Compiler type (e.g., gcc). If set to 'gcc', lcov will be used to generate coverage info",
    )
    parser.add_argument(
        "--api-source",
        type=str,
        choices=["shared-libs", "headers"],
        default="shared-libs",
        help="Source for API extraction: 'shared-libs' extracts from shared library exports "
             "(default), 'headers' parses header files directly (useful for C++ vtables where "
             "symbols may not be exported but are callable via vtable dispatch)",
    )
    parser.add_argument(
        "--headers-dir",
        type=str,
        default=None,
        help="Path to the directory containing header files. If not provided, defaults to "
             "install_dir/include (if exists) or install_dir",
    )
    parser.add_argument(
        "--build-dir",
        type=str,
        default=None,
        help="Path to the build directory (where compilation happened). "
             "If not provided, auto-detects from common locations: project root, "
             "project/build, project/_build, project/out, or install_dir",
    )

    args = parser.parse_args()

    # Validate project_dir exists
    project_dir = os.path.abspath(os.path.expanduser(args.project_dir))
    if not os.path.isdir(project_dir):
        logging.error(f"ERROR: project_dir does not exist: {args.project_dir}")
        sys.exit(1)

    # Validate api_key is not empty
    if not args.api_key or args.api_key.strip() == "":
        logging.error("ERROR: api_key is required but not provided")
        sys.exit(1)

    # Validate install_dir exists
    install_dir = os.path.abspath(os.path.expanduser(args.install_dir))
    if not os.path.isdir(install_dir):
        logging.error(f"ERROR: install_dir does not exist: {args.install_dir}")
        sys.exit(1)

    # Validate doxygen_path if provided
    if args.doxygen_path:
        doxygen_path = os.path.abspath(os.path.expanduser(args.doxygen_path))
        if not os.path.isdir(doxygen_path):
            logging.error(f"ERROR: doxygen_path does not exist: {args.doxygen_path}")
            sys.exit(1)

    # Validate headers_dir if provided
    if args.headers_dir:
        headers_dir = os.path.abspath(os.path.expanduser(args.headers_dir))
        if not os.path.isdir(headers_dir):
            logging.error(f"ERROR: headers_dir does not exist: {args.headers_dir}")
            sys.exit(1)

    # Determine build directory
    if args.build_dir:
        build_dir = os.path.abspath(os.path.expanduser(args.build_dir))
        if not os.path.isdir(build_dir):
            logging.warning(f"WARNING: Specified build_dir does not exist: {args.build_dir}")
            build_dir = None
        else:
            logging.info(f"Using specified build directory: {build_dir}")
    else:
        build_dir = None

    # If build_dir not specified or doesn't exist, search common locations
    if build_dir is None:
        candidate_dirs = [
            project_dir,
            os.path.join(project_dir, "build"),
            os.path.join(project_dir, "_build"),
            os.path.join(project_dir, "out"),
            install_dir, # Fallback to install dir
        ]

        for candidate in candidate_dirs:
            if os.path.isdir(candidate):
                build_dir = candidate
                logging.info(f"Auto-detected build directory: {build_dir}")
                break

        if build_dir is None:
            logging.warning("Could not find a valid build directory, using install_dir")
            build_dir = install_dir

    # Determine header search directory
    if args.headers_dir:
        header_search_dir = os.path.abspath(os.path.expanduser(args.headers_dir))
        logging.info(f"Using provided headers directory: {header_search_dir}")
    else:
        # Check if include directory exists within install_dir
        include_dir = os.path.join(install_dir, "include")
        if os.path.isdir(include_dir):
            header_search_dir = include_dir
            logging.debug(
                f"DEBUG: Found include directory, searching for headers in: {include_dir}"
            )
        else:
            header_search_dir = install_dir
            logging.debug(
                f"DEBUG: No include directory found, searching for headers in: {install_dir}"
            )

    header_files = find_header_files(header_search_dir)
    logging.info("Header files found: %s", header_files)

    # Save header files to JSON
    headers_file = os.path.join(project_dir, "headers.json")
    logging.debug("DEBUG: Writing header files to: %s", headers_file)
    headers_data = {"headers": header_files, "count": len(header_files)}
    with open(headers_file, "w") as fh:
        json.dump(headers_data, fh, indent=2)

    # Identify build system and extract linking flags
    build_system = identify_build_system(project_dir)
    logging.info(f"Detected build system: {build_system}")

    linking_flags = extract_linking_flags(build_dir, build_system, project_dir)
    logging.info(f"Linking flags found: {linking_flags}")

    # Save linking flags to JSON
    linking_flags_file = os.path.join(project_dir, "linking_flags.json")
    logging.debug("DEBUG: Writing linking flags to: %s", linking_flags_file)
    flag_count = len(linking_flags.split()) if linking_flags else 0
    linking_flags_data = {"linking_flags": linking_flags, "count": flag_count}
    with open(linking_flags_file, "w") as fh:
        json.dump(linking_flags_data, fh, indent=2)

    lib_exports = ExportFetcher()

    if args.api_source == "headers":
        # Header-based API extraction mode
        # Useful for C++ vtables where symbols may not be in shared lib exports
        logging.info("Using header-based API extraction mode")
        lib_exports.get_apis_from_headers(header_search_dir)
        logging.info("Total number of APIs found: %d", sum(len(apis) for apis in lib_exports.apis.values()))
    else:
        # Default: shared library export-based API extraction
        logging.info("Using shared library export-based API extraction mode")
        shared_libs = find_shared_libraries(install_dir)
        logging.debug("DEBUG: Shared libraries found: %s", shared_libs)

        for lib in shared_libs:
            lib_exports.get_exports_from_lib(lib)

        logging.debug("DEBUG: Total number of symbols found: %d", len(lib_exports.symbols))

        install_dir = os.path.abspath(os.path.expanduser(args.install_dir))
        lib_exports.filter_non_apis(install_dir)

        logging.info("Total number of APIs found: %d", sum(len(apis) for apis in lib_exports.apis.values()))
    json_data = {"apis": lib_exports.apis}
    api_file = os.path.join(project_dir, "apis.json")
    logging.debug("DEBUG: Writing APIs to:  %s", api_file)
    with open(api_file, "w") as fh:
        json.dump(json_data, fh)

    all_apis = []
    for file, apis in lib_exports.apis.items():
        for api in apis:
            all_apis.append(api)
    entry_cov = LibCoverage(all_apis, project_dir)
    logging.debug("DEBUG: Running gcov to identify API sizes and coverage")
    entry_cov.run_gcov_on_gcno_files()
    entry_cov.populate_entry_api_cov()

    if args.doxygen_path:
        logging.info("Doxygen path provided, generating API documentation")
        doxygen_path = os.path.abspath(os.path.expanduser(args.doxygen_path))
        doc_gen = DocGen(doxygen_path, xml=args.xml)
        apidoc = doc_gen.generate_apidoc(all_apis)
    else:
        logging.info("No Doxygen path provided, skipping API documentation generation")
        apidoc = None

    json_data = {}
    no_cov_apis = []
    no_doc_apis = []
    for file, apis in lib_exports.apis.items():
        json_data[file] = {}
        for api in apis:
            # Always create an entry for each API with default values
            json_data[file][api] = {
                "full_size": 0,
                "covered_lines": 0
            }
            
            if api in entry_cov.api_sizes:
                json_data[file][api]["full_size"] = entry_cov.api_sizes[api]
                json_data[file][api]["covered_lines"] = entry_cov.api_coverage[api]
            else:
                logging.error("ERROR: Failed to find size for API: %s", api)
                no_cov_apis.append(api)

            if apidoc and api in apidoc:
                json_data[file][api]["apidoc"] = apidoc[api]
            else:
                logging.debug("DEBUG: Failed to find documentation for API: %s", api)
                no_doc_apis.append(api)

    apicov_file = os.path.join(args.project_dir, "api_coverage.json")
    logging.info("Writing API data to: %s", apicov_file)
    with open(apicov_file, "w") as fh:
        json.dump(json_data, fh)

    if no_cov_apis:
        logging.warning(
            "Failed to find size for %d APIs: %s", len(no_cov_apis), no_cov_apis
        )

    if no_doc_apis:
        logging.warning(
            "Failed to find documentation for %d APIs: %s",
            len(no_doc_apis),
            no_doc_apis,
        )

    # Create archive for upload based on compiler type
    archive_path = None
    if args.compile and args.compile.lower() == "gcc":
        logging.info("Compiler type is gcc, using lcov to generate coverage info")
        baseline_info = os.path.join(project_dir, "baseline.info")
        if generate_lcov_info(project_dir, baseline_info):
            logging.debug("DEBUG: Creating lcov archive for upload")
            archive_path = compress_lcov_file(
                baseline_info,
                output_path=project_dir,
                archive_name="coverage_data.tar.xz",
            )
            if archive_path:
                logging.debug(f"DEBUG: Lcov archive created successfully: {archive_path}")
            else:
                logging.error("ERROR: Failed to create lcov archive")
        else:
            logging.error("ERROR: Failed to generate lcov info file")
    else:
        if args.compile:
            logging.debug(
                f"DEBUG: Compiler type '{args.compile}' is not gcc, skipping coverage file generation"
            )
        else:
            logging.debug(
                "DEBUG: No compiler type specified, skipping coverage file generation"
            )
        # Create an empty tar file to avoid uploading huge gcov files
        logging.debug("DEBUG: Creating empty archive placeholder")
        archive_path = os.path.join(project_dir, "coverage_data.tar.xz")
        try:
            with tarfile.open(archive_path, "w:xz"):
                pass  # Create empty archive
            logging.debug(f"DEBUG: Empty archive created: {archive_path}")
        except Exception as e:
            logging.error(f"ERROR: Failed to create empty archive: {e}")
            archive_path = None

    # Upload coverage data if API key is provided
    if args.api_key:
        logging.info("Uploading data to endpoint")
        upload_data(json_data, header_files, linking_flags, args.api_key, archive_path)


if __name__ == "__main__":
    main()
