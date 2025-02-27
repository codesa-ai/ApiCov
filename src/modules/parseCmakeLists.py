import os
import re

def parse_cmake_for_headers(cmake_file):
    """
    Parses a CMakeLists.txt file to identify header file directories.

    Args:
        cmake_file (str): The path to the CMakeLists.txt file.

    Returns:
        list: A list of directories containing header files.
    """
    header_dirs = set()
    include_dir_pattern = re.compile(r'include_directories\(([^)]+)\)', re.IGNORECASE)
    target_include_dir_pattern = re.compile(r'target_include_directories\([^)]+\s+PRIVATE\s+([^)]+)\)', re.IGNORECASE)

    with open(cmake_file, 'r') as file:
        for line in file:
            include_match = include_dir_pattern.search(line)
            target_include_match = target_include_dir_pattern.search(line)
            if include_match:
                dirs = include_match.group(1).split()
                for dir in dirs:
                    header_dirs.add(os.path.abspath(os.path.join(os.path.dirname(cmake_file), dir.strip())))
            elif target_include_match:
                dirs = target_include_match.group(1).split()
                for dir in dirs:
                    header_dirs.add(os.path.abspath(os.path.join(os.path.dirname(cmake_file), dir.strip())))

    return list(header_dirs)

def parse_cmake_for_install_dir(cmake_file):
    """
    Parses a CMakeLists.txt file to identify the default install directory.

    Args:
        cmake_file (str): The path to the CMakeLists.txt file.

    Returns:
        str: The default install directory, or None if not found.
    """
    install_dir_pattern = re.compile(r'set\s*\(\s*CMAKE_INSTALL_PREFIX\s+([^\s)]+)\s*\)', re.IGNORECASE)

    with open(cmake_file, 'r') as file:
        for line in file:
            install_match = install_dir_pattern.search(line)
            if install_match:
                install_dir = install_match.group(1).strip()
                return os.path.abspath(os.path.join(os.path.dirname(cmake_file), install_dir))

    return None

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse CMakeLists.txt to identify header file directories and the default install directory")
    parser.add_argument('cmake_file', type=str, help='Path to the CMakeLists.txt file')

    args = parser.parse_args()
    header_dirs = parse_cmake_for_headers(args.cmake_file)
    install_dir = parse_cmake_for_install_dir(args.cmake_file)

    print("Header directories found:")
    for dir in header_dirs:
        print(dir)

    if install_dir:
        print(f"Default install directory found: {install_dir}")
    else:
        print("Default install directory not found.")