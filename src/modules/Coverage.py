import os
import subprocess
from modules.logging_config import logging


class LibCoverage:
    """
    A class to analyze code coverage for library APIs using gcov data.
    
    This class provides functionality to extract and analyze code coverage information
    for library functions using gcov-generated data files (.gcno and .gcov_log files).
    It calculates entry-point coverage (direct function coverage) for individual APIs.
    
    The class supports:
    - Parsing gcov log files to extract coverage percentages and line counts
    - Calculating coverage for individual functions
    - Handling special cases like SDL libraries that use macro wrappers
    - Running gcov on .gcno files to generate coverage logs
    
    Attributes:
        _apis (List[str]): List of API function names to analyze
        api_coverage (Dict[str, float]): Dictionary mapping API names to coverage percentages
        _root_dir (str): Absolute path to the library root directory
        api_sizes (Dict[str, int]): Dictionary mapping API names to total line counts
        _fn_sizes (Dict[str, tuple]): Cache of function coverage data (covered_lines, total_lines)
        gcov_files (List[str]): List of all generated .gcov file paths
    
    Example:
        # Initialize with API list and library path
        apis = ["function1", "function2", "function3"]
        coverage = LibCoverage(apis, "/path/to/library")
        
        # Generate coverage logs from .gcno files
        coverage.run_gcov_on_gcno_files()
        
        # Calculate entry-point coverage for all APIs
        coverage.populate_entry_api_cov()
        
        # Get results
        print(coverage.api_coverage)
        print(coverage.api_sizes)
    
    Dependencies:
        - gcov: For generating coverage data from .gcno files
        - subprocess: For running gcov commands
        - os: For file system operations
    """
    def __init__(self, apis, lib_path):
        """
        Initialize the LibCoverage instance.
        
        Args:
            apis (List[str]): List of API function names to analyze for coverage
            lib_path (str): Path to the library root directory containing .gcno files
        """
        self._apis = apis
        self.api_coverage = {}
        self._root_dir = os.path.abspath(lib_path)
        self.api_sizes = {}
        self._fn_sizes = {}
        self.gcov_files = []  # Store all generated .gcov files

    def get_fn_size_and_cov(self, fn):
        """
        Extract coverage data for a specific function from gcov log files.
        
        This method searches for coverage information for the given function
        in .gcov_log files within the library directory. It parses the gcov
        output to extract both the total number of lines and the coverage percentage.
        
        Args:
            fn (str): Function name to search for in coverage logs
            
        Returns:
            tuple: (covered_lines, total_lines) where covered_lines is the number
                   of executed lines and total_lines is the total number of lines
        """
        logging.debug("Processing function: %s", fn)
        cmd = ["grep", "-A1", "-rw", fn, "--include=*.gcov_log", self._root_dir]
        results = subprocess.run(cmd, capture_output=True, text=True)
        if results.returncode != 0:
            # logging.warning("Error - grep failed for function: %s", fn)
            return 0, 0
        final_coverage = 0
        final_size = 0
        temp_coverage = None
        ignore_patterns = {"Cannot"}
        for line in results.stdout.split("\n"):
            if any(pattern in line for pattern in ignore_patterns):
                continue
            if "Lines executed" in line:
                # logging.debug("Line: %s", line)
                t = line.split("Lines executed")[-1]
                # logging.debug("T: %s", t)
                try:
                    coverage = t.split("%")[0].split(":")[-1].strip()
                    # logging.debug("coverage: %s", t.split("of")[0].strip())
                    temp_coverage = float(coverage.strip())
                except ValueError as e:
                    logging.warning(
                        "Failed to parse coverage from line: %s. Error: %s", line, e
                    )
                    temp_coverage = None

                if temp_coverage:
                    final_coverage = max(final_coverage, temp_coverage)
                    temp_coverage = None

            if " of " in line:
                s_size = line.split("of")[-1].strip()
                # logging.debug("size: %s", t.split("of")[-1].strip())
                size = int(s_size)
                final_size = max(final_size, size)

        if final_size == 0:
            logging.error("Zero size for function: %s", fn)

        if final_coverage > 100.00:
            logging.debug("Coverage greater than 100%")
            logging.debug("%s", results.stdout)

            covered_lines = final_size
        else:
            covered_lines = (final_coverage / 100) * final_size

        return covered_lines, final_size

    def get_api_coverage(self, api):
        """
        Calculate entry-point coverage for a single API function.
        
        This method extracts coverage information for the specified API function
        directly from gcov log files, without considering its callees. It searches
        for the function name in .gcov_log files and parses the coverage percentage
        and line count.
        
        Args:
            api (str): API function name to calculate coverage for
        """
        cmd = ["grep", "-A1", "-rw", api, "--include=*.gcov_log", self._root_dir]
        results = subprocess.run(cmd, capture_output=True, text=True)
        for line in results.stdout.split("\n"):
            if "Cannot" in line:
                continue
            if "Lines executed" in line:
                t = line.split(":")[-1]
                coverage = t.split("of")[0].strip()
                size = int(t.split("of")[-1].strip())
                # logging.debug("Coverage string: %s", coverage.strip("%"))
                float_cov = float(coverage.strip("%"))
                # logging.debug("Float value: %r", float_cov)
                if float_cov > 100.00:
                    logging.warning("Error - coverage greater than 100%")
                    logging.debug("%s", results.stdout)
                    float_cov = 100.00

                line_cov = int((float_cov * size) / 100)
                if api.endswith("_REAL"):
                    api = api.replace("_REAL", "")
                if api in self.api_coverage:
                    new_val = line_cov
                    if new_val > self.api_coverage[api]:
                        self.api_coverage[api] = new_val
                else:
                    self.api_coverage[api] = line_cov

                if api in self.api_sizes:
                    if self.api_sizes[api] < size:
                        self.api_sizes[api] = size
                else:
                    self.api_sizes[api] = size
            # if "No executable lines" in line:
            #     return

    def populate_entry_api_cov(self, sdl=False):
        """
        Calculate entry-point coverage for all APIs.
        
        This method processes all APIs in the instance and calculates their
        direct coverage (without considering callees). It handles special cases
        for SDL libraries that use macro wrappers with _REAL suffix.
        
        Args:
            sdl (bool): Whether this is an SDL library (uses macro wrappers with _REAL suffix)
        """
        # SDL uses macros for all APIs almost
        # to find the real cov value we have to append REAL
        # to the api name
        for api in self._apis:
            if sdl:
                self.get_api_coverage(api + "_REAL")
            self.get_api_coverage(api)

    def get_gcno_files(self):
        """
        Find all .gcno files in the library directory.
        
        This method recursively searches the library directory for all .gcno files,
        which are gcov data files containing coverage information.
        
        Returns:
            List[str]: List of absolute paths to all .gcno files found
        """
        gcno_files = []
        for root, dirs, files in os.walk(self._root_dir):
            for file in files:
                if file.endswith(".gcno"):
                    gcno_files.append(os.path.join(root, file))
        return gcno_files

    def filter_errors(self, lines):
        """
        Filter out common error messages from gcov output.
        
        This method removes error messages that are not relevant to coverage
        analysis, such as "No such file or directory" and "Not a directory"
        messages that gcov may produce.
        
        Args:
            lines (str): Raw output from gcov command
            
        Returns:
            str: Filtered output with error messages removed
        """
        filtered_lines = []
        for line in lines.splitlines():
            if "No such file or directory" in line or "Not a directory" in line:
                continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines)

    def run_gcov_on_gcno_files(self):
        """
        Run gcov on all .gcno files to generate coverage logs and .gcov files.
        
        This method processes all .gcno files found in the library directory
        and runs gcov on each one to generate corresponding .gcov_log files
        and .gcov files. The gcov output is filtered to remove irrelevant 
        error messages. All generated .gcov files are stored in self.gcov_files.
        """
        gcno_files = self.get_gcno_files()
        for file in gcno_files:
            file_dir = os.path.split(file)[0]
            filename = os.path.split(file)[-1]
            logging.debug("FileName: %s", filename)
            if filename.startswith("."):
                continue
            logging.debug("Processing gcno file: %s", file)
            log_file = file.replace(".gcno", ".gcov_log")
            cmd = ["gcov", "-l", "-f", filename]  # Added -l option to include source code
            p = subprocess.run(cmd, cwd=file_dir, capture_output=True, text=True)
            with open(log_file, "w") as fh:
                fh.write(self.filter_errors(p.stdout))
            
            # Store all generated .gcov files for this .gcno file
            for gcov_file in os.listdir(file_dir):
                if gcov_file.endswith(".gcov"):
                    gcov_path = os.path.join(file_dir, gcov_file)
                    if gcov_path not in self.gcov_files:
                        self.gcov_files.append(gcov_path)
                        logging.debug("Added .gcov file: %s", gcov_path)