import os
import zipfile
import tempfile
import tarfile
from pathlib import Path
from modules.logging_config import logging


def identify_build_system(project_dir):
    """
    Identifies the build system used in the given project directory.

    Args:
        project_dir (str): The path to the project directory.

    Returns:
        str: The name of the build system ('cmake', 'meson', 'make', 'ninja', or 'unknown').
    """
    if os.path.exists(os.path.join(project_dir, "CMakeLists.txt")):
        return "cmake"
    elif os.path.exists(os.path.join(project_dir, "meson.build")):
        return "meson"
    elif os.path.exists(os.path.join(project_dir, "Makefile")):
        return "make"
    elif os.path.exists(os.path.join(project_dir, "build.ninja")):
        return "ninja"
    else:
        return "unknown"


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
        dirnames[:] = [d for d in dirnames if not d.startswith(".")] + [
            d for d in dirnames if d.startswith(".")
        ]
        for filename in filenames:
            if filename.endswith(".so"):
                shared_libs.append(os.path.join(dirpath, filename))
    return shared_libs


def compress_gcov_files(gcov_files: list[str], output_path: str | None = None, archive_name: str="coverage_data.tgz") -> str:
    """
    Compress all .gcov files into a tar.gz (.tgz) archive for upload.
    Only .tgz or .tar.gz extensions are supported.
    """
    if not gcov_files:
        logging.warning("No .gcov files provided for compression")
        return None
    # Determine output directory
    if output_path is None:
        output_path = os.getcwd()  # Use current working directory instead of temp directory
    # Create output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)
    # Full path for the archive file
    archive_file_path = os.path.join(output_path, archive_name)
    logging.info(f"Compressing {len(gcov_files)} .gcov files into {archive_file_path}")
    try:
        if archive_name.endswith(".tgz") or archive_name.endswith(".tar.gz"):
            with tarfile.open(archive_file_path, "w:gz") as tarf:
                for gcov_file in gcov_files:
                    if not os.path.exists(gcov_file):
                        logging.warning(f"Gcov file not found: {gcov_file}")
                        continue
                    file_path = Path(gcov_file)
                    arcname = file_path.name
                    tarf.add(gcov_file, arcname=arcname)
                    logging.debug(f"Added to archive: {gcov_file} -> {arcname}")
        else:
            raise ValueError(f"Unsupported archive extension for {archive_file_path}. Only .tgz or .tar.gz are supported.")
        logging.info(f"Successfully created gcov archive: {archive_file_path}")
        logging.info(f"Archive size: {os.path.getsize(archive_file_path)} bytes")
        return archive_file_path
    except Exception as e:
        logging.error(f"Failed to create gcov archive: {e}")
        raise
