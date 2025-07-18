import os
import zipfile
import tempfile
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


def compress_gcov_files(gcov_files, output_path=None, archive_name="gcov_files.zip"):
    """
    Compress all .gcov files into a zip archive for upload.
    
    This function takes a list of .gcov file paths and creates a compressed
    zip archive containing all the files. The archive can be used for
    uploading coverage data to a server.
    
    Args:
        gcov_files (List[str]): List of paths to .gcov files to compress
        output_path (str, optional): Directory where the zip file should be created.
                                    If None, uses a temporary directory.
        archive_name (str, optional): Name of the zip archive file. Defaults to "gcov_files.zip".
    
    Returns:
        str: Path to the created zip archive file
        
    Raises:
        FileNotFoundError: If any of the .gcov files don't exist
        OSError: If there are issues creating the zip file
    """
    if not gcov_files:
        logging.warning("No .gcov files provided for compression")
        return None
    
    # Determine output directory
    if output_path is None:
        output_path = tempfile.gettempdir()
    
    # Create output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)
    
    # Full path for the zip file
    zip_file_path = os.path.join(output_path, archive_name)
    
    logging.info(f"Compressing {len(gcov_files)} .gcov files into {zip_file_path}")
    
    try:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for gcov_file in gcov_files:
                if not os.path.exists(gcov_file):
                    logging.warning(f"Gcov file not found: {gcov_file}")
                    continue
                
                # Get the relative path for the archive (preserve directory structure)
                file_path = Path(gcov_file)
                arcname = file_path.name  # Just the filename, not the full path
                
                zipf.write(gcov_file, arcname)
                logging.debug(f"Added to archive: {gcov_file} -> {arcname}")
        
        logging.info(f"Successfully created gcov archive: {zip_file_path}")
        logging.info(f"Archive size: {os.path.getsize(zip_file_path)} bytes")
        
        return zip_file_path
        
    except Exception as e:
        logging.error(f"Failed to create gcov archive: {e}")
        raise
