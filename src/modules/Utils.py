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


def _add_files_to_tar(tarf, gcov_files, root_dir):
    """
    Add gcov files to a tar archive with proper path handling.
    
    Args:
        tarf: TarFile object to add files to
        gcov_files: List of gcov file paths
        root_dir: Root directory for resolving relative paths
    """
    for gcov_file in gcov_files:
        # Resolve the full path if root_dir is provided
        if root_dir and not os.path.isabs(gcov_file):
            full_gcov_path = os.path.join(root_dir, gcov_file)
        else:
            full_gcov_path = gcov_file
        
        if not os.path.exists(full_gcov_path):
            logging.warning(f"Gcov file not found: {gcov_file}")
            continue
        
        # Truncate the filename to be relative to the library root
        # Full filename: #home#ahmedzaki#benchmark_libs#FFmpeg#libavutil#tests#bprint.gcno##libavutil#bprint.h.gcov
        # We want: libavutil#tests#bprint.gcno##libavutil#bprint.h.gcov
        if root_dir:
            root_dir_name = os.path.basename(root_dir)
            # Split by the root directory name to get the part after it
            parts = gcov_file.split(f"#{root_dir_name}#")
            if len(parts) > 1:
                # Take everything after the root directory name
                arcname = parts[1]
            else:
                # Fallback: if we can't find the root dir name, use the original filename
                arcname = gcov_file
        else:
            arcname = gcov_file
        
        tarf.add(full_gcov_path, arcname=arcname)
        logging.debug(f"Added to archive: {full_gcov_path} -> {arcname}")


def compress_gcov_files(gcov_files: list[str], output_path: str | None = None, archive_name: str="coverage_data.tar.xz", root_dir: str = None) -> str:
    """
    Compress all .gcov files into a tar.xz archive for upload.
    Uses xz compression which provides much better compression ratios than gzip.
    
    Args:
        gcov_files (list[str]): List of gcov file paths (can be relative or absolute)
        output_path (str, optional): Output directory for the archive. Defaults to current directory.
        archive_name (str): Name of the archive file. Defaults to "coverage_data.tar.xz".
        root_dir (str, optional): Root directory to resolve relative paths. If None, assumes paths are absolute.
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
        # Use xz compression for much better compression ratios
        if archive_name.endswith(".tar.xz") or archive_name.endswith(".txz"):
            import lzma
            with tarfile.open(archive_file_path, "w:xz", preset=9) as tarf:  # Maximum xz compression
                _add_files_to_tar(tarf, gcov_files, root_dir)
        
        # Fallback to gzip if xz is not available or for .tgz files
        elif archive_name.endswith(".tgz") or archive_name.endswith(".tar.gz"):
            with tarfile.open(archive_file_path, "w:gz", compresslevel=9) as tarf:  # Maximum gzip compression
                _add_files_to_tar(tarf, gcov_files, root_dir)
        else:
            raise ValueError(f"Unsupported archive extension for {archive_file_path}. Supported: .tar.xz, .txz, .tgz, .tar.gz")
        
        final_size = os.path.getsize(archive_file_path)
        logging.info(f"Successfully created archive: {archive_file_path}")
        logging.info(f"Archive size: {final_size} bytes")
        return archive_file_path
        
    except Exception as e:
        logging.error(f"Failed to create archive: {e}")
        raise
