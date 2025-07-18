import os
import subprocess
from modules.logging_config import logging


class LibCoverage:
    """
    A class to analyze code coverage for library APIs using gcov data.
    
    This class provides functionality to extract and analyze code coverage information
    for library functions using gcov-generated data files (.gcno and .gcov_log files).
    It can calculate both entry-point coverage (direct function coverage) and full
    coverage including all callees in the call graph.
    
    The class supports:
    - Parsing gcov log files to extract coverage percentages and line counts
    - Calculating coverage for individual functions
    - Computing full API coverage including all functions in the call graph
    - Handling special cases like SDL libraries that use macro wrappers
    - Running gcov on .gcno files to generate coverage logs
    
    Attributes:
        _apis (List[str]): List of API function names to analyze
        api_coverage (Dict[str, float]): Dictionary mapping API names to coverage percentages
        _root_dir (str): Absolute path to the library root directory
        api_sizes (Dict[str, int]): Dictionary mapping API names to total line counts
        _fn_sizes (Dict[str, tuple]): Cache of function coverage data (covered_lines, total_lines)
    
    Example:
        # Initialize with API list and library path
        apis = ["function1", "function2", "function3"]
        coverage = LibCoverage(apis, "/path/to/library")
        
        # Generate coverage logs from .gcno files
        coverage.run_gcov_on_gcno_files()
        
        # Calculate full coverage including call graph
        callgraph = load_callgraph_from_file()
        coverage.populate_full_api_cov(callgraph)
        
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

    def dfs(self, function, callgraph, all_callees):
        """
        Perform depth-first search to find all callees in the call graph.
        
        This method recursively traverses the call graph starting from a given
        function to find all functions that are called (directly or indirectly)
        by the starting function.
        
        Args:
            function (str): Starting function name for the DFS traversal
            callgraph (Dict[str, List[str]]): Call graph mapping functions to their callees
            all_callees (List[str]): List to accumulate all discovered callees
        """
        all_callees.append(function)
        for callee in callgraph[function]:
            if callee not in all_callees:
                self.dfs(callee, callgraph, all_callees)

    def get_api_callgraph(self, api, callgraph):
        """
        Get all functions in the call graph for a given API.
        
        This method uses depth-first search to find all functions that are
        called (directly or indirectly) by the specified API function.
        
        Args:
            api (str): API function name to find callees for
            callgraph (Dict[str, List[str]]): Call graph mapping functions to their callees
            
        Returns:
            List[str]: List of all functions in the call graph for the given API
        """
        all_callees = []
        if api in callgraph:
            self.dfs(api, callgraph, all_callees)

        return all_callees

    def get_full_api_cov(self, api, callees):
        """
        Calculate full coverage for an API including all its callees.
        
        This method computes the total coverage for an API by summing up the
        coverage of all functions in its call graph (the API itself plus all
        functions it calls directly or indirectly).
        
        Args:
            api (str): API function name
            callees (List[str]): List of all functions in the API's call graph
        """
        total_covered_lines = 0
        total_size = 0
        for call in callees:
            if call not in self._fn_sizes:
                covered_lines, size = self.get_fn_size_and_cov(call)
                self._fn_sizes[call] = (covered_lines, size)
            else:
                covered_lines = self._fn_sizes[call][0]
                size = self._fn_sizes[call][1]
            total_covered_lines += covered_lines
            total_size += size

        try:
            float_cov = (total_covered_lines / total_size) * 100
        except ZeroDivisionError:
            logging.warning("Error - Zero division error for API: %s", api)
            # sys.exit()
            float_cov = 0.0

        if api.endswith("_REAL"):
            api = api.replace("_REAL", "")
        if api in self.api_coverage:
            new_val = float_cov
            if new_val > self.api_coverage[api]:
                self.api_coverage[api] = new_val
        else:
            self.api_coverage[api] = float_cov

        if api in self.api_sizes:
            if self.api_sizes[api] < total_size:
                self.api_sizes[api] = total_size
        else:
            self.api_sizes[api] = total_size

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

    def populate_full_api_cov(self, callgraph, sdl=False):
        """
        Calculate full coverage for all APIs including their call graphs.
        
        This method processes all APIs in the instance and calculates their
        full coverage by including all functions in their respective call graphs.
        It handles special cases for SDL libraries that use macro wrappers.
        
        Args:
            callgraph (Dict[str, List[str]]): Call graph mapping functions to their callees
            sdl (bool): Whether this is an SDL library (uses macro wrappers with _REAL suffix)
        """
        for api in self._apis:
            if sdl:
                callees = self.get_api_callgraph(api + "_REAL", callgraph)
                self.get_full_api_cov(api + "_REAL", callees)
            callees = self.get_api_callgraph(api, callgraph)
            self.get_full_api_cov(api, callees)

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
        Run gcov on all .gcno files to generate coverage logs.
        
        This method processes all .gcno files found in the library directory
        and runs gcov on each one to generate corresponding .gcov_log files.
        The gcov output is filtered to remove irrelevant error messages.
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
            cmd = ["gcov", "-f", filename]
            p = subprocess.run(cmd, cwd=file_dir, capture_output=True, text=True)
            with open(log_file, "w") as fh:
                fh.write(self.filter_errors(p.stdout))