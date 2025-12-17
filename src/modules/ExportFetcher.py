import re
import os
import sys
import json
import subprocess

from modules.logging_config import logging

from modules.Utils import CXX_HEADERS_EXT, C_HEADERS_EXT, ALL_HEADERS_EXT

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
        self.function_names = set()  # Track already seen function names

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
                        if file in self.apis:
                            if symbol not in self.apis[file]:
                                self.apis[file].append(symbol)
                        else:
                            self.apis[file] = [symbol]
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
        
        # Common standard library and system functions to exclude
        # These are often called within inline functions in headers
        stdlib_functions = {
            # C standard library
            'printf', 'fprintf', 'sprintf', 'snprintf', 'scanf', 'fscanf', 'sscanf',
            'malloc', 'calloc', 'realloc', 'free', 'memcpy', 'memmove', 'memset', 'memcmp',
            'strcpy', 'strncpy', 'strcat', 'strncat', 'strcmp', 'strncmp', 'strlen', 'strstr',
            'strcpy_s', 'strncpy_s', 'strcat_s', 'strncat_s',
            'fopen', 'fclose', 'fread', 'fwrite', 'fgets', 'fputs', 'fseek', 'ftell',
            'exit', 'abort', 'atexit', 'getenv', 'setenv', 'system',
            'assert', 'static_assert',
            # Dynamic loading
            'dlopen', 'dlclose', 'dlsym', 'dlerror',
            # Windows API
            'LoadLibrary', 'LoadLibraryA', 'LoadLibraryW', 'FreeLibrary', 'GetProcAddress',
            'GetLastError', 'SetLastError', 'GetModuleHandle', 'GetModuleHandleA', 'GetModuleHandleW',
            'SetEnvironmentVariable', 'SetEnvironmentVariableA', 'SetEnvironmentVariableW',
            'GetEnvironmentVariable', 'GetEnvironmentVariableA', 'GetEnvironmentVariableW',
            # POSIX
            'open', 'close', 'read', 'write', 'stat', 'fstat', 'lstat',
            # C++ keywords that might match
            'if', 'while', 'for', 'switch', 'return', 'sizeof', 'typeof', 'alignof',
            'new', 'delete', 'throw', 'catch', 'try',
        }
        
        # Pattern for C-style function declarations at file/namespace scope
        # Matches: [export_macro] return_type function_name(params);
        # The key is requiring proper return type (not just any identifier)
        c_pattern = r"^\s*(?:\w+\s+)*?(?:extern\s+)?(?:const\s+)?(?:unsigned\s+|signed\s+)?(?:void|int|char|short|long|float|double|bool|size_t|ssize_t|\w+_t|\w+\*+)\s+\*?\s*(\w+)\s*\([^)]*\)\s*;"
        
        # Pattern for functions with explicit export macros (most reliable indicator of public API)
        # Matches: EXPORT_MACRO return_type function_name(params);
        export_pattern = r"^\s*[A-Z][A-Z0-9_]*(?:PUBLIC|EXPORT|API|DLLPUBLIC|VISIBLE)\w*\s+[\w\s*&]+?\s+\*?\s*(\w+)\s*\([^)]*\)\s*;"
        
        # Pattern for C++ method declarations (including virtual methods for vtables)
        # Matches: virtual return_type method_name(params) [const] [= 0];
        cpp_pattern = r"^\s*(?:virtual\s+)(?:const\s+)?[\w\s*&]+?\s+[*&]?\s*(\w+)\s*\([^)]*\)\s*(?:const)?\s*(?:override)?\s*(?:=\s*0)?\s*;"
        
        # Pattern for function pointer typedefs in structs (vtable style APIs)
        # Matches: return_type (*function_name) (params);
        vtable_pattern = r"^\s*[\w\s*]+?\s+\(\*\s*(\w+)\s*\)\s*\([^)]*\)\s*;"
        
        # Pattern for C++ class methods with inline bodies
        # Matches: return_type method_name(params) { ... } or return_type method_name(params) const { ... }
        # The [*&]?\s* handles pointer/reference attached to function name (e.g., Type *get() {})
        cpp_inline_pattern = r"^\s*(?:virtual\s+)?(?:static\s+|inline\s+)?(?:const\s+)?[\w\s*&:<>]+?\s+[*&]?\s*(\w+)\s*\([^)]*\)\s*(?:const)?\s*(?:override)?\s*(?:noexcept)?\s*\{"
        
        # Pattern for multi-line function declarations (captures function name from first line)
        # Matches: return_type function_name( on its own line (params continue on next lines)
        multiline_pattern = r"^\s*(?:virtual\s+)?(?:static\s+|inline\s+)?(?:const\s+)?[\w\s*&:<>]+?\s+[*&]?\s*(\w+)\s*\([^)]*,$"
        
        for pattern in [export_pattern, c_pattern, cpp_pattern, vtable_pattern, cpp_inline_pattern, multiline_pattern]:
            regex = re.compile(pattern, re.MULTILINE)
            matches = regex.findall(file_data)
            for function_name in matches:
                fn_name = function_name.strip()
                # Skip standard library and system functions
                if fn_name in stdlib_functions:
                    continue
                # Skip very short names (likely false positives)
                if len(fn_name) < 2:
                    continue
                # Skip names that are all uppercase (likely macros)
                if fn_name.isupper():
                    continue
                # Skip names that look like member variables (common C++ naming conventions)
                # Patterns: mFoo, mpFoo, pFoo, m_foo (Hungarian notation style)
                if len(fn_name) > 2:
                    # mpFoo pattern (member pointer)
                    if fn_name.startswith('mp') and fn_name[2].isupper():
                        continue
                    # mFoo pattern (member variable)  
                    if fn_name[0] == 'm' and fn_name[1].isupper():
                        continue
                    # pFoo pattern (pointer parameter in initializer lists)
                    if fn_name[0] == 'p' and fn_name[1].isupper():
                        continue
                    # m_foo pattern (underscore style)
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

        Args:
            header_dir (str): The root directory containing header files.

        Returns:
            list: List of API function names found in headers.
        """

        apis = {}
        
        for root, _, files in os.walk(header_dir):
            for file in files:
                if (any(file.endswith(ext) for ext in ALL_HEADERS_EXT)):
                    header_path = os.path.join(root, file)
                    logging.debug("DEBUG: Parsing header file for APIs: %s", header_path)
                    try:
                        with open(header_path, 'r', encoding='utf-8', errors='ignore') as fh:
                            file_data = fh.read()
                            # Remove single-line comments
                            file_data = re.sub(r'//.*$', '', file_data, flags=re.MULTILINE)
                            # Remove multi-line comments
                            file_data = re.sub(r'/\*.*?\*/', '', file_data, flags=re.DOTALL)
                            # Remove preprocessor macros that span multiple lines
                            file_data = re.sub(r'#.*?(?<!\\)\n', '\n', file_data)
                            
                            found = self.find_functions_in_file(file_data)
                            if found:
                                logging.debug("DEBUG: Found %d functions in %s", len(found), header_path)
                                if file.endswith(tuple(CXX_HEADERS_EXT)):
                                    if "cxx_apis" not in apis:
                                        apis["cxx_apis"] = {}
                                    apis["cxx_apis"][file] = found
                                if file.endswith(tuple(C_HEADERS_EXT)):
                                    if "c_apis" not in apis:
                                        apis["c_apis"] = {}
                                    apis["c_apis"][file] = found
                    except Exception as e:
                        logging.warning("Failed to parse header %s: %s", header_path, e)
        
        # In header mode, all found symbols are considered APIs
        # Merge all category dictionaries (cxx_apis, c_apis) into self.apis
        self.apis = {}
        for category_apis in apis.values():
            self.apis.update(category_apis)
        logging.info("Extracted APIs from %d header files", len(self.apis))
        for file, apis in self.apis.items():
            logging.info("Found %d APIs in %s", len(apis), file)
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
            # This is a c++ symbol
            if line.find("@@") != -1:
                line = line.split("@@")[0]

            line = line.strip()
            if "::" in line:
                # if line.find("operator") != -1:
                #     continue
                pattern = r"\w+::(\w+)[\(\[]"
                regex = re.compile(pattern, re.M)
                matches = regex.findall(line)
                for symbol in matches:
                    self._add_symbol(symbol)
            elif line:
                symbol = line.split()[-1]
                if symbol == "":
                    continue
                self._add_symbol(symbol)
        # proc2 = subprocess.Popen(grep_command, stdin=proc1.stdout, stdout=subprocess.PIPE)
        # proc1.stdout.close()
        return proc2.returncode

if __name__ == "__main__":
    d = ExportFetcher()
    # d.crawl_dir(sys.argv[1], sys.argv[2])
    # print(d.function_names)

    json_data = {}
    exports = []

    headers_dir = sys.argv[1]
    d.get_apis_from_headers(headers_dir)
    json_data["apis"] = d.apis
    with open("apis.json", "w") as fh:
        json.dump(json_data, fh)

    

    # shared_libs = sys.argv[1].split(",")
    # for lib in shared_libs:
    #     d.get_exports_from_lib(lib)

    # install_dirs = sys.argv[2].split(",")
    # for install_dir in install_dirs:
    #     d.filter_non_apis(install_dir)
    # json_data["library"] = d.apis
    # with open("apis.json", "w") as fh:
    #     json.dump(json_data, fh)

    # with open("apis.txt", "w") as fh:
    #     for fn in d.apis:
    #         fh.write(fn + "\n")
