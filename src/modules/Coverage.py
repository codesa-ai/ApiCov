import os 
import subprocess
import sys
import re
import json
import logging
from collections import defaultdict
from modules.logging_config import logging 


class LibCoverage():

    def __init__(self, apis, lib_path):
        self._apis = apis
        self.api_coverage = {}
        self._root_dir = os.path.abspath(lib_path)
        self.api_sizes = {}
        self._fn_sizes = {}
    
    def get_fn_size_and_cov(self, fn):
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
        for line in results.stdout.split('\n'):
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
                    logging.warning("Failed to parse coverage from line: %s. Error: %s", line, e)
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
            covered_lines = (final_coverage/100) * final_size
        
        return covered_lines, final_size

    def dfs(self, function, callgraph, all_callees):
        all_callees.append(function)
        for callee in callgraph[function]:
            if callee not in all_callees:
                self.dfs(callee, callgraph, all_callees)

    def get_api_callgraph(self, api, callgraph):
        all_callees = []
        if api in callgraph:
            self.dfs(api, callgraph, all_callees)
        
        return all_callees

    def get_full_api_cov(self, api, callees):
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
            float_cov = (total_covered_lines/total_size) * 100
        except ZeroDivisionError:
            logging.warning("Error - Zero division error for API: %s", api)
            # sys.exit()
            float_cov = 0.0

        if api.endswith("_REAL"):
            api = api.replace("_REAL","")
        if api in self.api_coverage:
            new_val = float_cov
            if new_val > self.api_coverage[api][0]:
                self.api_coverage[api] = (new_val, total_size)
        else:
            self.api_coverage[api] = (float_cov, total_size)
        
        if api in self.api_sizes:
            if self.api_sizes[api] < total_size:
                self.api_sizes[api] = total_size
        else:
            self.api_sizes[api] = total_size        
        
    def get_api_coverage(self, api):
        cmd = ["grep", "-A1", "-rw", api, "--include=*.gcov_log", self._root_dir]
        results = subprocess.run(cmd, capture_output=True, text=True)
        for line in results.stdout.split('\n'):
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

                if api.endswith("_REAL"):
                    api = api.replace("_REAL","")
                if api in self.api_coverage:
                    new_val = float_cov
                    if new_val > self.api_coverage[api][0]:
                        self.api_coverage[api] = (new_val, size)
                else:
                    self.api_coverage[api] = (float_cov, size)
                
                if api in self.api_sizes:
                    if self.api_sizes[api] < size:
                        self.api_sizes[api] = size
                else:
                    self.api_sizes[api] = size
            # if "No executable lines" in line:
            #     return
    
    def populate_full_api_cov(self, callgraph, sdl=False):
        for api in self._apis:
            if sdl:
                callees = self.get_api_callgraph(api+"_REAL", callgraph)
                self.get_full_api_cov(api+"_REAL", callees)
            callees = self.get_api_callgraph(api, callgraph)
            self.get_full_api_cov(api, callees)

    def populate_entry_api_cov(self, sdl=False):
        # SDL uses macros for all APIs almost
        # to find the real cov value we have to append REAL
        # to the api name
        for api in self._apis:
            if sdl:
                self.get_api_coverage(api+"_REAL")
            self.get_api_coverage(api)
            
    def get_gcno_files(self):
        gcno_files = []
        for root, dirs, files in os.walk(self._root_dir):
            for file in files:
                if file.endswith(".gcno"):
                    gcno_files.append(os.path.join(root, file))
        return gcno_files

    def filter_errors(self, lines):
        filtered_lines = []
        for line in lines.splitlines():
            if "No such file or directory" in line or "Not a directory" in line:
                continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines)

    def run_gcov_on_gcno_files(self):
        gcno_files =self.get_gcno_files()
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


def merge_callgraphs(callgraphs):
    merged = {}
    for graph in callgraphs:
        for api in graph:
            if api in merged:
                merged[api].extend(graph[api])
            else:
                merged[api] = graph[api]
    return merged

if __name__ == "__main__":

    lib_path = sys.argv[1]
    functions_json = sys.argv[2]
    path = "/tmp/data/libraries/xiph@@vorbis"
    callgraphs = []
    shared_libs = ["libvorbis.so","libvorbisenc.so","libvorbisfile.so "]
    for shared_lib in shared_libs:
        shared_lib = shared_lib.strip()
        callgraph_file = os.path.join(path, shared_lib+"_callgraph.txt")
        if os.path.exists(callgraph_file):
            logging.debug("Processing callgraph file: %s", callgraph_file)
            g = CallGraphParser(callgraph_file)
            callgraphs.append(g.parse_callgraph())
    
    callgraph = merge_callgraphs(callgraphs)

    # callgraph_file = sys.argv[3]
    with open(functions_json, 'r') as fh:
        data = json.load(fh)
    exports = list(data.values())
    # graph = CallGraphParser(callgraph_file)
    # callgraph = graph.parse_callgraph()

    c = LibCoverage(exports[0], lib_path)
    c.run_gcov_on_gcno_files()
    c.populate_full_api_cov(callgraph)
    with open('api_coverage.json', 'w') as fh:
        json.dump(c.api_coverage, fh)
    with open('api_sizes.json', 'w') as fh:
        json.dump(c.api_sizes, fh)
