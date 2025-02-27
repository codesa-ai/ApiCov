import os
import logging

from modules.logging_config import logging 


def identify_build_system(project_dir):
    """
    Identifies the build system used in the given project directory.

    Args:
        project_dir (str): The path to the project directory.

    Returns:
        str: The name of the build system ('cmake', 'meson', 'make', 'ninja', or 'unknown').
    """
    if os.path.exists(os.path.join(project_dir, 'CMakeLists.txt')):
        return 'cmake'
    elif os.path.exists(os.path.join(project_dir, 'meson.build')):
        return 'meson'
    elif os.path.exists(os.path.join(project_dir, 'Makefile')):
        return 'make'
    elif os.path.exists(os.path.join(project_dir, 'build.ninja')):
        return 'ninja'
    else:
        return 'unknown'

def find_shared_libraries(root_dir):
    """
    Finds all shared library files (.so) in the given root directory, including hidden folders.

    Args:
        root_dir (str): The path to the root directory.

    Returns:
        list: A list of fully qualified paths to the shared library files.
    """
    shared_libs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Include hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith('.')] + [d for d in dirnames if d.startswith('.')]
        for filename in filenames:
            if filename.endswith('.so'):
                shared_libs.append(os.path.join(dirpath, filename))
    return shared_libs