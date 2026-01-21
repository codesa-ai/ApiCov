import re
import os
import sys
import json
import subprocess

from modules.logging_config import logging

from modules.Utils import CXX_HEADERS_EXT, C_HEADERS_EXT, ALL_HEADERS_EXT
from modules.ClangParser import ClangParser, is_cpp_header, CLANG_AVAILABLE

class ExportFetcher(object):
    """
    A class to extract and filter exported API symbols from shared libraries and header files.

    This class provides functionality to:
    - Extract exported function symbols from shared libraries using nm and grep
    - Filter out non-API symbols by searching for their presence in header files
    - Identify function declarations in header files using regex
    - Support various build systems for header discovery and installation

    Attributes:
        symbols (List[str]): All discovered symbols from shared libraries
        apis (List[str]): Filtered list of API symbols present in headers
        headers (List[str]): List of header file paths found in the install directory

    Example:
        fetcher = ExportFetcher()
        fetcher.get_exports_from_lib("/path/to/libfoo.so")
        fetcher.filter_non_apis("/path/to/install/include")
        print(fetcher.apis)

    Dependencies:
        - nm, grep: For extracting and filtering symbols from shared libraries
        - subprocess: For running shell commands
        - os, re: For file and regex operations
    """

    def __init__(self):
        self.symbols = []
        self.apis = {}
        self.headers = []
        self.function_names = set()

    def grep_for_symbol(self, symbol: str, install_dir: str) -> None:
        """
        Search recursively for a given symbol in all header files (.h, .hpp, .hxx) within the specified install directory.
        If the symbol is found in any header, it is added to the list of API symbols (self.apis).

        Args:
            symbol (str): The symbol name to search for.
            install_dir (str): The root directory to search for header files.
        """
        for root, _, files in os.walk(install_dir):
            for file in files:
                if (any(file.endswith(ext) for ext in ALL_HEADERS_EXT)):
                    header = os.path.join(root, file)
                    logging.debug(
                        "DEBUG: Searching for symbol: %s in header: %s", symbol, header
                    )
                    cmd = ["grep", "-rw", symbol, header]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("Adding Api: %s", symbol)
                        # Create structured API data
                        api_data = {
                            "qualified": symbol,  # No qualified name from grep, use simple name
                            "simple": symbol,
                            "signature": ""  # No signature from grep
                        }

                        if file in self.apis:
                            # Check if this symbol already exists
                            existing_names = [api["simple"] for api in self.apis[file]]
                            if symbol not in existing_names:
                                self.apis[file].append(api_data)
                        else:
                            self.apis[file] = [api_data]
                        return

    def filter_non_apis(self, install_dir: str) -> None:
        """
        Filter the list of discovered symbols (self.symbols) to retain only those that are present in the header files
        of the given install directory. Uses grep_for_symbol for each symbol.

        Args:
            install_dir (str): The root directory to search for header files.
        """
        for symbol in self.symbols:
            self.grep_for_symbol(symbol, os.path.abspath(install_dir))

    def find_functions_in_file(self, file_data: str) -> list:
        """
        Use a regular expression to find C/C++ function declarations in the provided file data (as a string).
        Adds any new function names found to the list of discovered symbols (self.symbols).

        Args:
            file_data (str): The contents of a header file.

        Returns:
            list: List of function names found in the file.
        """
        found_functions = []

        stdlib_functions = {
            'printf', 'fprintf', 'sprintf', 'snprintf', 'scanf', 'fscanf', 'sscanf',
            'malloc', 'calloc', 'realloc', 'free', 'memcpy', 'memmove', 'memset', 'memcmp',
            'strcpy', 'strncpy', 'strcat', 'strncat', 'strcmp', 'strncmp', 'strlen', 'strstr',
            'strcpy_s', 'strncpy_s', 'strcat_s', 'strncat_s',
            'fopen', 'fclose', 'fread', 'fwrite', 'fgets', 'fputs', 'fseek', 'ftell',
            'exit', 'abort', 'atexit', 'getenv', 'setenv', 'system',
            'assert', 'static_assert',
            'dlopen', 'dlclose', 'dlsym', 'dlerror',
            'LoadLibrary', 'LoadLibraryA', 'LoadLibraryW', 'FreeLibrary', 'GetProcAddress',
            'GetLastError', 'SetLastError', 'GetModuleHandle', 'GetModuleHandleA', 'GetModuleHandleW',
            'SetEnvironmentVariable', 'SetEnvironmentVariableA', 'SetEnvironmentVariableW',
            'GetEnvironmentVariable', 'GetEnvironmentVariableA', 'GetEnvironmentVariableW',
            'open', 'close', 'read', 'write', 'stat', 'fstat', 'lstat',
            'if', 'while', 'for', 'switch', 'return', 'sizeof', 'typeof', 'alignof',
            'new', 'delete', 'throw', 'catch', 'try',
        }

        c_pattern = r"^\s*(?:\w+\s+)*?(?:extern\s+)?(?:const\s+)?(?:unsigned\s+|signed\s+)?(?:void|int|char|short|long|float|double|bool|size_t|ssize_t|\w+_t|\w+\*+)\s+\*?\s*(\w+)\s*\([^)]*\)\s*;"
        export_pattern = r"^\s*[A-Z][A-Z0-9_]*(?:PUBLIC|EXPORT|API|DLLPUBLIC|VISIBLE)\w*\s+[\w\s*&]+?\s+\*?\s*(\w+)\s*\([^)]*\)\s*;"
        cpp_pattern = r"^\s*(?:virtual\s+)(?:const\s+)?[\w\s*&]+?\s+[*&]?\s*(\w+)\s*\([^)]*\)\s*(?:const)?\s*(?:override)?\s*(?:=\s*0)?\s*;"
        vtable_pattern = r"^\s*[\w\s*]+?\s+\(\*\s*(\w+)\s*\)\s*\([^)]*\)\s*;"
        cpp_inline_pattern = r"^\s*(?:virtual\s+)?(?:static\s+|inline\s+)?(?:const\s+)?[\w\s*&:<>]+?\s+[*&]?\s*(\w+)\s*\([^)]*\)\s*(?:const)?\s*(?:override)?\s*(?:noexcept)?\s*\{"
        multiline_pattern = r"^\s*(?:virtual\s+)?(?:static\s+|inline\s+)?(?:const\s+)?[\w\s*&:<>]+?\s+[*&]?\s*(\w+)\s*\([^)]*,$"

        for pattern in [export_pattern, c_pattern, cpp_pattern, vtable_pattern, cpp_inline_pattern, multiline_pattern]:
            regex = re.compile(pattern, re.MULTILINE)
            matches = regex.findall(file_data)
            for function_name in matches:
                fn_name = function_name.strip()
                if fn_name in stdlib_functions:
                    continue
                if len(fn_name) < 2:
                    continue
                if fn_name.isupper():
                    continue
                if len(fn_name) > 2:
                    if fn_name.startswith('mp') and fn_name[2].isupper():
                        continue
                    if fn_name[0] == 'm' and fn_name[1].isupper():
                        continue
                    if fn_name[0] == 'p' and fn_name[1].isupper():
                        continue
                    if fn_name.startswith('m_'):
                        continue
                if fn_name not in found_functions:
                    found_functions.append(fn_name)
        
        return list(set(found_functions))

    def get_apis_from_headers(self, header_dir: str) -> list:
        """
        Extract API function names directly from header files in the given directory.
        This mode is useful for C++ code with vtables where symbols may not be exported
        in shared libraries but are still callable via vtable dispatch.

        For C++ headers, uses libclang for accurate parsing when available.
        Falls back to regex-based parsing for C headers or if libclang fails.

        Args:
            header_dir (str): The root directory containing header files.

        Returns:
            dict: Dictionary mapping header files to lists of API info dicts.
                  Each API info dict contains: qualified_name, simple_name, signature
        """

        apis = {}
        clang_parser = None

        # Initialize ClangParser if available
        if CLANG_AVAILABLE:
            try:
                clang_parser = ClangParser(header_dirs=[header_dir])
                logging.info("Using libclang for C++ header parsing")
            except Exception as e:
                logging.warning(f"Could not initialize ClangParser: {e}. Falling back to regex.")

        for root, _, files in os.walk(header_dir):
            for file in files:
                if (any(file.endswith(ext) for ext in ALL_HEADERS_EXT)):
                    header_path = os.path.join(root, file)
                    logging.debug("DEBUG: Parsing header file for APIs: %s", header_path)

                    # Try libclang for C++ headers
                    if clang_parser and is_cpp_header(header_path):
                        try:
                            api_info_dict = clang_parser.parse_header(header_path)
                            if api_info_dict:
                                # Convert ApiInfo objects to structured dicts
                                api_list = []
                                for api_info in api_info_dict.values():
                                    api_list.append({
                                        "qualified": api_info.qualified_name,
                                        "simple": api_info.simple_name,
                                        "signature": api_info.signature or ""
                                    })

                                if api_list:
                                    apis[file] = api_list
                                    logging.debug(f"DEBUG: ClangParser found {len(api_list)} functions in {header_path}")
                                    continue  # Successfully parsed with clang, skip regex
                        except Exception as e:
                            logging.warning(f"ClangParser failed for {header_path}: {e}. Falling back to regex.")

                    # Fallback to regex-based parsing (for C headers or if clang failed)
                    try:
                        with open(header_path, 'r', encoding='utf-8', errors='ignore') as fh:
                            file_data = fh.read()
                            file_data = re.sub(r'//.*$', '', file_data, flags=re.MULTILINE)
                            file_data = re.sub(r'/\*.*?\*/', '', file_data, flags=re.DOTALL)
                            file_data = re.sub(r'#.*?(?<!\\)\n', '\n', file_data)

                            found = self.find_functions_in_file(file_data)
                            if found:
                                logging.debug("DEBUG: Regex found %d functions in %s", len(found), header_path)
                                # Convert to structured format (regex can't extract qualified names or signatures)
                                api_list = []
                                for func_name in found:
                                    api_list.append({
                                        "qualified": func_name,  # No qualified name from regex
                                        "simple": func_name,
                                        "signature": ""  # No signature from regex
                                    })
                                apis[file] = api_list
                    except Exception as e:
                        logging.warning("Failed to parse header %s: %s", header_path, e)

        # Store in self.apis
        self.apis = apis
        logging.info("Extracted APIs from %d header files", len(self.apis))
        for file, api_list in self.apis.items():
            logging.info("Found %d APIs in %s", len(api_list), file)
        return self.apis

    def _add_symbol(self, symbol: str) -> None:
        """
        Add a symbol to the list of discovered symbols (self.symbols) if it is not already present.

        Args:
            symbol (str): The symbol name to add.
        """
        if symbol not in self.symbols:
            self.symbols.append(symbol)

    def get_exports_from_lib(self, shared_lib: str) -> int:
        """
        Extract exported symbols from a shared library using the nm and grep commands. Filters for symbols of type
        " T " (text section, i.e., functions), ignores C++ operators and certain mangled names, and adds discovered
        symbols to self.symbols.

        Args:
            shared_lib (str): Path to the shared library file.

        Returns:
            int: The return code from the grep command.

        Raises:
            subprocess.CalledProcessError: If the nm or grep command fails.
        """
        nm_command = ["nm", "-D", "-C", "--defined-only", shared_lib]
        grep_command = ["grep", " T "]
        logging.debug("DEBUG: Running: %s", " ".join(nm_command))
        proc1 = subprocess.run(nm_command, stdout=subprocess.PIPE)
        logging.debug("DEBUG: Running: %s", "".join(grep_command))
        proc2 = subprocess.run(
            grep_command,
            input=proc1.stdout.decode("utf-8"),
            capture_output=True,
            text=True,
        )
        for line in proc2.stdout.split("\n"):
            if line.find("operator") != -1:
                continue
            if line.find("mangle_path") != -1:
                continue
            if line.find("@@") != -1:
                line = line.split("@@")[0]

            line = line.strip()
            if "::" in line:
                # Extract qualified C++ name (namespace::Class::method)
                # Changed from r"\w+::(\w+)[\(\[]" to preserve full qualified name
                pattern = r"([\w:]+)[\(\[]"
                regex = re.compile(pattern, re.M)
                matches = regex.findall(line)
                for qualified_name in matches:
                    # Extract simple name (last component after ::)
                    simple_name = qualified_name.split('::')[-1]
                    # Store simple name for backward compatibility with filter_non_apis
                    self._add_symbol(simple_name)
            elif line:
                symbol = line.split()[-1]
                if symbol == "":
                    continue
                self._add_symbol(symbol)
        return proc2.returncode

if __name__ == "__main__":
    d = ExportFetcher()

    json_data = {}
    exports = []

    headers_dir = sys.argv[1]
    d.get_apis_from_headers(headers_dir)
    json_data["apis"] = d.apis
    with open("apis.json", "w") as fh:
        json.dump(json_data, fh)
