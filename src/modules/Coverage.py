import os
import re
import subprocess
import shutil
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
        self.gcov_files = []
        self._has_cxxfilt = shutil.which("c++filt") is not None
        if not self._has_cxxfilt:
            logging.warning("c++filt not found - C++ mangled names will not be demangled")

    def get_fn_size_and_cov(self, fn: str) -> tuple[int, int]:
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
        logging.debug("DEBUG: Processing function: %s", fn)
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
            logging.error("ERROR: Zero size for function: %s", fn)

        if final_coverage > 100.00:
            logging.debug("DEBUG: Coverage greater than 100%")
            logging.debug("DEBUG: %s", results.stdout)

            covered_lines = final_size
        else:
            covered_lines = (final_coverage / 100) * final_size

        return covered_lines, final_size

    def set_api_coverage(self, api: str) -> None:
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
                    logging.debug("DEBUG: Coverage greater than 100%")
                    logging.debug("DEBUG: %s", results.stdout)
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

    def populate_entry_api_cov(self, sdl: bool = False) -> None:
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
                self.set_api_coverage(api + "_REAL")
            self.set_api_coverage(api)

    def get_gcno_files(self) -> list[str]:
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

    def _extract_function_name(self, name: str) -> tuple[str, str]:
        """
        Extract both qualified and simple function/method names from a potentially demangled C++ name.

        This method is backwards compatible with C code:
        - C functions pass through unchanged (no ::, no mangling)
        - C++ demangled names are split into qualified and simple forms

        Examples:
            C:   'my_function' -> ('my_function', 'my_function')
            C:   'SDL_Init' -> ('SDL_Init', 'SDL_Init')
            C++: 'lok::Document::saveAs(char const*, char const*)' -> ('lok::Document::saveAs', 'saveAs')
            C++: 'namespace::Class::method()' -> ('namespace::Class::method', 'method')
            C++: 'std::vector<int>::push_back(int)' -> ('std::vector::push_back', 'push_back')

        Args:
            name (str): Function name (C) or demangled C++ function name

        Returns:
            tuple[str, str]: (qualified_name, simple_name)
                qualified_name: Full namespace::Class::method without parameters
                simple_name: Just the method name without namespace, class, or parameters
        """
        # For plain C functions without any special characters, return as-is for both
        # This ensures backwards compatibility with C code
        if '::' not in name and '(' not in name and '<' not in name:
            return (name, name)

        clean_name = re.sub(r'<[^>]*>', '', name)

        # Find the last occurrence of '(' to separate function name from parameters
        # This handles cases like "(anonymous namespace)::function(params)"
        last_paren = clean_name.rfind('(')

        if last_paren != -1:
            # Everything before the last '(' is the qualified name
            qualified_name = clean_name[:last_paren].strip()
        else:
            qualified_name = clean_name.strip()

        # Handle operator overloads (keep the operator part)
        if 'operator' in qualified_name:
            # Extract operator and its symbol
            match = re.search(r'(operator\S+)', qualified_name)
            if match:
                operator_name = match.group(1)
                # For qualified, keep full path to operator
                return (qualified_name, operator_name)

        # Get the last component after :: for simple name
        simple_name = qualified_name
        if '::' in simple_name:
            simple_name = simple_name.split('::')[-1]

        # Safety check: never return empty simple name
        if not simple_name:
            # Fallback to qualified name or original input
            simple_name = qualified_name if qualified_name else name.split('(')[0] if '(' in name else name

        return (qualified_name, simple_name)

    def demangle_cxx_names(self, text: str) -> str:
        """
        Demangle C++ mangled names in the given text using c++filt and extract
        just the function/method names.

        This method is backwards compatible with C code:
        - C function names are not mangled and pass through unchanged
        - C++ mangled names (starting with _Z) are demangled and simplified

        C++ compilers mangle function names (e.g., _ZN3lok8Document7saveAsEPKcS2_S2_
        becomes lok::Document::saveAs). This method demangles names and extracts
        just the method name (saveAs) to match our header-based API extraction.

        Args:
            text (str): Text potentially containing mangled C++ names

        Returns:
            str: Text with C++ names demangled to just method names,
                 C names are unchanged
        """
        if not self._has_cxxfilt:
            return text

        try:
            result = subprocess.run(
                ["c++filt"],
                input=text,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                logging.warning("c++filt failed, using original text")
                return text

            # Process each line and simplify demangled names to just function names
            output_lines = []
            for line in result.stdout.splitlines():
                if line.startswith("Function '") and line.endswith("'"):
                    # Extract the demangled name
                    demangled = line[10:-1]  # Remove "Function '" and trailing "'"
                    qualified_name, simple_name = self._extract_function_name(demangled)
                    # For gcov matching, use simple_name (backward compatible)
                    output_lines.append(f"Function '{simple_name}'")
                else:
                    output_lines.append(line)

            return "\n".join(output_lines)

        except subprocess.TimeoutExpired:
            logging.warning("c++filt timed out, using original text")
            return text
        except Exception as e:
            logging.warning(f"c++filt error: {e}, using original text")
            return text

    def filter_errors(self, lines: str) -> str:
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

    def run_gcov_on_gcno_files(self) -> None:
        """
        Run gcov on all .gcno files to generate coverage logs and .gcov files.

        This method processes all .gcno files found in the library directory
        and runs gcov on each one to generate corresponding .gcov_log files
        and .gcov files. The gcov output is filtered to remove irrelevant
        error messages. After all gcov runs are complete, all .gcov files
        are collected from the root directory.
        """
        gcno_files = self.get_gcno_files()
        logging.info(f"Found {len(gcno_files)} .gcno files to process")

        # Run gcov on all .gcno files
        for file in gcno_files:
            filename = os.path.split(file)[-1]
            logging.debug("DEBUG: FileName: %s", filename)
            if filename.startswith("."):
                continue
            logging.debug("DEBUG: Processing gcno file: %s", file)
            log_file = file.replace(".gcno", ".gcov_log")

            # Run gcov with options to include source code
            cmd = ["gcov", "-f", "-p", file]
            logging.debug(f"DEBUG: Running gcov command: {' '.join(cmd)}")
            p = subprocess.run(cmd, cwd=self._root_dir, capture_output=True, text=True)

            # DEBUG: Show what happened
            logging.debug(f"DEBUG: gcov return code: {p.returncode}")
            logging.debug(f"DEBUG: gcov stdout: {p.stdout[:500]}")
            if p.stderr:
                logging.debug(f"DEBUG: gcov stderr: {p.stderr}")

            # Filter errors and demangle C++ names before writing
            filtered_output = self.filter_errors(p.stdout)
            demangled_output = self.demangle_cxx_names(filtered_output)

            with open(log_file, "w") as fh:
                fh.write(demangled_output)

        # Collect all .gcov files after all gcov runs are complete
        logging.debug("DEBUG: Collecting all .gcov files")
        for gcov_file in os.listdir(self._root_dir):
            if gcov_file.endswith(".gcov"):
                self.gcov_files.append(gcov_file)
                logging.debug("DEBUG: Added .gcov file: %s", gcov_file)

        logging.debug(f"DEBUG: Collected {len(self.gcov_files)} .gcov files")
