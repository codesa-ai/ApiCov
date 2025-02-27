import re
import os
import sys
import logging
import json
import subprocess

from modules.logging_config import logging 

class ExportFetcher(object):
    def __init__(self, project_dir):
        self.symbols = []
        self.apis = []
        self._root_dir = os.path.abspath(project_dir)
        self.headers = []

    def grep_for_symbol(self, symbol, install_dir):
        for root, _, files in os.walk(install_dir):
            for file in files:
                if file.endswith(".h") or file.endswith(".hpp") or file.endswith(".hxx"):
                    header = os.path.join(root, file)
                    logging.debug("Searching for symbol: %s in header: %s", symbol, header)
                    cmd = ["grep", "-rw", symbol, header]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.debug("Adding Api: %s", symbol)
                        self.apis.append(symbol)
                        return

    def filter_non_apis(self, install_dir):
        for symbol in self.symbols:
            self.grep_for_symbol(symbol, os.path.abspath(install_dir))

    def find_functions_in_file(self, file_data):
        pattern = r'(?:\s*(static\s+|inline\s+|virtual\s+)?)?([\w\s*]+?)\s+([\w_]+)\s*\(([^)]*)\)\s*(?:const)?\s*(?:volatile)?\s*;'
        functions = re.compile(pattern, re.M)
        matches = functions.findall(file_data)
        if matches:
            for match in matches:
                _, _, function_name, _ = match
                if function_name not in self.function_names:
                    self.symbols.append(function_name.strip())

    def _add_functions(self, output):
        for line in output.split('\n'):
            api = line.split(":")[-1]
            if api == '':
                continue
            if api not in self.function_names:
                self.symbols.append(api.strip())

    def _walk_dir(self, dir, compile_commands):
        includes="-I"
        includes += " -I".join(IMPORTS)
        for root, dirs, files in os.walk(dir):
            for file in files:
                if file.endswith(".h") or file.endswith(".hpp") or file.endswith(".hxx"):
                    path = os.path.join(root, file)
                    command = [LIBTOOL, "-p", compile_commands, path, "--", includes]
                    res = run_command(command, os.getcwd(), shell=False)
                    if not res:
                        logging.error("Failed to process: %s", path)
                        with open(path, 'r') as fh:
                            self.find_functions_in_file(fh.read())
                        continue
                    self._add_functions(res.stdout)

    def crawl_dir(self, dir, compile_commands):
        self._walk_dir(dir, compile_commands)

    def _add_symbol(self, symbol):
        if symbol not in self.symbols:
            self.symbols.append(symbol)
 
    def get_exports_from_lib(self, shared_lib):
        """
        Extracts exported symbols from a shared library using the `nm` and `grep` commands.

        Args:
            shared_lib (str): The path to the shared library file.

        Returns:
            str: The output from the `grep` command containing the filtered symbols.

        Raises:
            subprocess.CalledProcessError: If either the `nm` or `grep` command fails.

        Notes:
            - This function uses the `nm` command to list symbols from the shared library.
            - The `grep` command filters the symbols to include only those with a " T " type.
            - C++ symbols are further processed to extract demangled names.
            - Symbols containing "operator" or "mangle_path" are ignored.
        """
        nm_command = ["nm", "-D", "--defined-only", shared_lib]
        grep_command = ["grep", " T "]
        logging.debug("Running: %s", ' '.join(nm_command))
        proc1 = subprocess.run(nm_command, stdout=subprocess.PIPE)
        logging.debug("Running: %s", ''.join(grep_command))
        proc2 = subprocess.run(grep_command, input=proc1.stdout.decode('utf-8'), capture_output=True, text=True)
        for line in proc2.stdout.split('\n'):
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
                pattern= r'\w+::(\w+)[\(\[]'
                regex = re.compile(pattern, re.M)
                matches = regex.findall(line)
                for symbol in matches:
                    self._add_symbol(symbol)
            elif line:
                symbol = line.split()[-1]
                if symbol == '':
                    continue
                self._add_symbol(symbol)
       # proc2 = subprocess.Popen(grep_command, stdin=proc1.stdout, stdout=subprocess.PIPE)
        # proc1.stdout.close()
        return proc2.returncode

    def find_build_dir(self):
        """
        Finds the build directory within the project directory.

        Returns:
            str: The path to the build directory, or the root directory if no specific build directory is found.
        """
        common_build_dirs = ['build', 'out', 'bin']
        for build_dir in common_build_dirs:
            potential_dir = os.path.join(self._root_dir, build_dir)
            if os.path.isdir(potential_dir):
                return potential_dir

        # Recursively search for specific build system files
        for dirpath, _, filenames in os.walk(self._root_dir):
            if 'CMakeCache.txt' in filenames or 'build.ninja' in filenames:
                return dirpath

        return self._root_dir
                    
    def get_install_headers(self, build_system):
        build_dir = self.find_build_dir()
        if build_system in ["make", "cmake"]:
            cmd = ["make", "install", "-n"]
        elif build_system == "ninja":
            cmd = ["ninja", "install", "-n"]
        elif build_system == "meson":
            cmd = ["meson", "install", "--dry-run"]
        else:
            raise ValueError("Unsupported build system")

        logging.debug("Running cmd: %s in %s", ' '.join(cmd), build_dir)
        result = subprocess.run(cmd, cwd=build_dir, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error("Failed to run dry-run install command")
            return

        for line in result.stdout.split('\n'):
            print(line)
            if line.endswith(".h") or line.endswith(".hpp") or line.endswith(".hxx"):

                self.headers.append(line.strip())

    def run_install_command(self, build_system):
        """
        Runs the install command to ensure the installation happens in /usr/local.

        Args:
            build_system (str): The build system used (e.g., 'make', 'ninja', 'meson').

        Raises:
            ValueError: If the build system is unsupported.
        """
        build_dir = self.find_build_dir()
        env = os.environ.copy()
        env['DESTDIR'] = '/usr/local'

        if build_system in ["make", "cmake"]:
            cmd = ["make", "install"]
        elif build_system == "ninja":
            cmd = ["ninja", "install"]
        elif build_system == "meson":
            cmd = ["meson", "install"]
        else:
            raise ValueError("Unsupported build system")

        logging.debug("Running install cmd: %s in %s", ' '.join(cmd), build_dir)
        result = subprocess.run(cmd, cwd=build_dir, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error("Failed to run install command")
            raise subprocess.CalledProcessError(result.returncode, cmd)
    
if __name__=="__main__":
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
    with open('apis.json', 'w') as fh:
        json.dump(json_data, fh)
    
    with open('apis.txt', "w") as fh:
        for fn in d.apis:
            fh.write(fn+"\n")
        
    
