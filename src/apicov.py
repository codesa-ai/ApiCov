import argparse
import json
import os
from modules.ExportFetcher import ExportFetcher
from modules.Utils import find_shared_libraries
from modules.Coverage import LibCoverage
from modules.logging_config import logging 

def main():
    parser = argparse.ArgumentParser(description="Code SA API Coverage Tool")
    parser.add_argument('project_dir', type=str, help='Path to the root directory')
    parser.add_argument('install_dir', type=str, help='Path to where the exported header files are installed')

    args = parser.parse_args()


    logging.debug("Looking for shared libraries in the project directory")
    shared_libs = find_shared_libraries(args.project_dir)

    logging.info("Shared libraries found: %s", shared_libs)

    logging.debug("Identifying exports from shared libraries")
    lib_exports = ExportFetcher()
    for lib in shared_libs:
        lib_exports.get_exports_from_lib(lib)

    logging.info("Total number of symbols found: %d", len(lib_exports.symbols))

    logging.debug("Filtering non-API exports")
    lib_exports.filter_non_apis(args.install_dir)

    logging.info("Total number of APIs found: %d", len(lib_exports.apis))
    json_data = {"apis": lib_exports.apis}
    api_file = os.path.join(args.project_dir, 'apis.json')
    logging.debug("Writing APIs to:  %s", api_file)
    with open(api_file, 'w') as fh:
        json.dump(json_data, fh)
    
    entry_cov = LibCoverage(lib_exports.apis, args.project_dir)
    logging.info("Running gcov to identify API sizes and coverage")
    entry_cov.run_gcov_on_gcno_files()
    logging.info("Populate API sizes and coverage")
    entry_cov.populate_entry_api_cov()

    json_data = {}
    failed_apis = []
    for api in lib_exports.apis:
        if api in entry_cov.api_sizes:
            json_data[api] = {}
            json_data[api]["full_size"] = entry_cov.api_sizes[api]
            json_data[api]["covered_lines"] = entry_cov.api_coverage[api]
        else:
            logging.error("Failed to find size for API: %s", api)
            failed_apis.append(api)
    apicov_file = os.path.join(args.project_dir, 'api_coverage.json')
    logging.info("Writing API coverage to: %s",apicov_file)
    with open(apicov_file, 'w') as fh:
        json.dump(json_data, fh)



if __name__ == "__main__":
    main()