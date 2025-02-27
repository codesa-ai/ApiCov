import re
import logging
from collections import defaultdict
from modules.logging_config import logging 


class CallGraphParser():
    # A parser for LLVM call graph files.

    # This class provides functionality to parse a call graph file produced by LLVM's opt tool and create a mapping of functions and their callees. It also includes a method to determine if a function is an LLVM internal function based on its name.

    # Attributes:
    #     _callgraph_file (str): The path to the call graph file to be parsed.

    # Methods:
    #     __init__(callgraph_file):
    #         Initializes the CallGraphParser with the given call graph file path.

    #     is_llvm_function(function_name):

    #     parse_callgraph():
    #         Parses the call graph file and creates a mapping of functions and their callees, excluding LLVM internal functions.

    def __init__(self, callgraph_file):
        self._callgraph_file = callgraph_file

    def is_llvm_function(self, function_name):
        """
        Determines if a function is an LLVM internal function based on its name.
        """
        llvm_patterns = [
            r"^llvm\.",    # Matches 'llvm.*' functions
            r"^__llvm_",   # Matches '__llvm_*' functions
            r"^_Z",        # Matches C++ mangled names starting with '_Z'
        ]
        return any(re.match(pattern, function_name) for pattern in llvm_patterns)


    def parse_callgraph(self):
        """
        Parses the callgraph.txt file produced by LLVM's opt tool and creates a mapping of functions and their callees.
        """
        callgraph = defaultdict(list)
        current_function = None

        with open(self._callgraph_file, "r") as file:
            for line in file:
                # Match the function definition
                match_func = re.match(r"^Call graph node for function: '(.+)'", line)
                if match_func:
                    current_function = match_func.group(1)
                    callgraph[current_function] = []
                    continue

                # Match the functions called by the current function
                match_called = re.match(r"^  CS<[^>]+> calls function '(.+)'", line)
                if match_called and current_function:
                    callee = match_called.group(1)
                    if not self.is_llvm_function(callee):  # Exclude LLVM functions
                        callgraph[current_function].append(callee)                

        return callgraph