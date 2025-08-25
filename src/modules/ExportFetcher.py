import re
import os
import sys
import json
import subprocess

from modules.logging_config import logging


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
        self.apis = []
        self.headers = []

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
                if (
                    file.endswith(".h")
                    or file.endswith(".hpp")
                    or file.endswith(".hxx")
                ):
                    header = os.path.join(root, file)
                    logging.debug(
                        "Searching for symbol: %s in header: %s", symbol, header
                    )
                    cmd = ["grep", "-rw", symbol, header]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("Adding Api: %s", symbol)
                        self.apis.append(symbol)
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

    def find_functions_in_file(self, file_data: str) -> None:
        """
        Use a regular expression to find C/C++ function declarations in the provided file data (as a string).
        Adds any new function names found to the list of discovered symbols (self.symbols).

        Args:
            file_data (str): The contents of a header file.
        """
        pattern = r"(?:\s*(static\s+|inline\s+|virtual\s+)?)?([\w\s*]+?)\s+([\w_]+)\s*\(([^)]*)\)\s*(?:const)?\s*(?:volatile)?\s*;"
        functions = re.compile(pattern, re.M)
        matches = functions.findall(file_data)
        if matches:
            for match in matches:
                _, _, function_name, _ = match
                if function_name not in self.function_names:
                    self.symbols.append(function_name.strip())

    def _add_functions(self, output: str) -> None:
        """
        Process the output (string) from a command or file, extracting function names (APIs) from each line and adding
        them to the list of discovered symbols (self.symbols) if not already present.

        Args:
            output (str): Output containing function names, one per line.
        """
        for line in output.split("\n"):
            api = line.split(":")[-1]
            if api == "":
                continue
            if api not in self.function_names:
                self.symbols.append(api.strip())

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
        nm_command = ["nm", "-D", "--defined-only", shared_lib]
        grep_command = ["grep", " T "]
        logging.debug("Running: %s", " ".join(nm_command))
        proc1 = subprocess.run(nm_command, stdout=subprocess.PIPE)
        logging.debug("Running: %s", "".join(grep_command))
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

    def find_build_dir(self) -> str:
        """
        Attempt to locate the build directory within the project by checking common directory names (build, out, bin)
        and by searching for build system files (CMakeCache.txt, build.ninja). Returns the path to the build directory
        or the root directory if none is found.

        Returns:
            str: Path to the build directory.
        """
        common_build_dirs = ["build", "out", "bin"]
        for build_dir in common_build_dirs:
            potential_dir = os.path.join(self._root_dir, build_dir)
            if os.path.isdir(potential_dir):
                return potential_dir

        # Recursively search for specific build system files
        for dirpath, _, filenames in os.walk(self._root_dir):
            if "CMakeCache.txt" in filenames or "build.ninja" in filenames:
                return dirpath

        return self._root_dir

    def get_install_headers(self, build_system: str) -> None:
        """
        Run the appropriate dry-run install command for the given build system to discover which header files would be
        installed. Populates self.headers with the paths of header files.

        Args:
            build_system (str): The build system in use (make, cmake, ninja, or meson).

        Raises:
            ValueError: If the build system is unsupported.
        """
        build_dir = self.find_build_dir()
        if build_system in ["make", "cmake"]:
            cmd = ["make", "install", "-n"]
        elif build_system == "ninja":
            cmd = ["ninja", "install", "-n"]
        elif build_system == "meson":
            cmd = ["meson", "install", "--dry-run"]
        else:
            raise ValueError("Unsupported build system")

        logging.debug("Running cmd: %s in %s", " ".join(cmd), build_dir)
        result = subprocess.run(cmd, cwd=build_dir, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error("Failed to run dry-run install command")
            return

        for line in result.stdout.split("\n"):
            if line.endswith(".h") or line.endswith(".hpp") or line.endswith(".hxx"):
                self.headers.append(line.strip())

    def run_install_command(self, build_system: str) -> None:
        """
        Run the actual install command for the given build system, setting the DESTDIR environment variable to
        /usr/local to control the installation location.

        Args:
            build_system (str): The build system in use (make, cmake, ninja, or meson).

        Raises:
            ValueError: If the build system is unsupported.
            subprocess.CalledProcessError: If the install command fails.
        """
        build_dir = self.find_build_dir()
        env = os.environ.copy()
        env["DESTDIR"] = "/usr/local"

        if build_system in ["make", "cmake"]:
            cmd = ["make", "install"]
        elif build_system == "ninja":
            cmd = ["ninja", "install"]
        elif build_system == "meson":
            cmd = ["meson", "install"]
        else:
            raise ValueError("Unsupported build system")

        logging.debug("Running install cmd: %s in %s", " ".join(cmd), build_dir)
        result = subprocess.run(
            cmd, cwd=build_dir, env=env, capture_output=True, text=True
        )
        if result.returncode != 0:
            logging.error("Failed to run install command")
            raise subprocess.CalledProcessError(result.returncode, cmd)


if __name__ == "__main__":
    d = ExportFetcher()
    # d.crawl_dir(sys.argv[1], sys.argv[2])
    # print(d.function_names)

    json_data = {}
    exports = []
    shared_libs = sys.argv[1].split(",")
    for lib in shared_libs:
        d.get_exports_from_lib(lib)

    install_dirs = sys.argv[2].split(",")
    for install_dir in install_dirs:
        d.filter_non_apis(install_dir)
    json_data["library"] = d.apis
    with open("apis.json", "w") as fh:
        json.dump(json_data, fh)

    with open("apis.txt", "w") as fh:
        for fn in d.apis:
            fh.write(fn + "\n")
