import os
import tarfile
from modules.logging_config import logging


CXX_HEADERS_EXT = ['.hpp', '.hxx', '.h++', '.hh']
C_HEADERS_EXT = ['.h']
ALL_HEADERS_EXT = CXX_HEADERS_EXT + C_HEADERS_EXT

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


def find_header_files(root_dir):
    """
    Finds all C and C++ header files in the given root directory, including hidden folders.

    Args:
        root_dir (str): The path to the root directory.

    Returns:
        list: A list of relative paths to the header files from the root directory.
    """


    headers = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in ALL_HEADERS_EXT):
                # Get relative path from root_dir
                rel_path = os.path.relpath(os.path.join(dirpath, filename), root_dir)
                headers.append(rel_path)
    return headers


def compress_lcov_file(
    info_file: str,
    output_path: str | None = None,
    archive_name: str = "coverage_data.tar.xz",
) -> str:
    """
    Compress an lcov .info file into a tar.xz archive for upload.
    Uses xz compression which provides much better compression ratios than gzip.

    Args:
        info_file (str): Path to the lcov .info file
        output_path (str, optional): Output directory for the archive. Defaults to same directory as info_file.
        archive_name (str): Name of the archive file. Defaults to "coverage_data.tar.xz".

    Returns:
        str: Path to the created archive file, or None if failed
    """
    if not info_file or not os.path.exists(info_file):
        logging.error(f"Info file does not exist: {info_file}")
        return None

    # Determine output directory
    if output_path is None:
        output_path = os.path.dirname(info_file) or os.getcwd()

    # Create output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)

    # Full path for the archive file
    archive_file_path = os.path.join(output_path, archive_name)
    logging.info(f"Compressing lcov info file into {archive_file_path}")

    try:
        # Use xz compression for much better compression ratios
        if archive_name.endswith(".tar.xz") or archive_name.endswith(".txz"):
            with tarfile.open(
                archive_file_path, "w:xz", preset=9
            ) as tarf:  # Maximum xz compression
                tarf.add(info_file, arcname=os.path.basename(info_file))

        # Fallback to gzip if xz is not available or for .tgz files
        elif archive_name.endswith(".tgz") or archive_name.endswith(".tar.gz"):
            with tarfile.open(
                archive_file_path, "w:gz", compresslevel=9
            ) as tarf:  # Maximum gzip compression
                tarf.add(info_file, arcname=os.path.basename(info_file))
        else:
            raise ValueError(
                f"Unsupported archive extension for {archive_file_path}. Supported: .tar.xz, .txz, .tgz, .tar.gz"
            )

        final_size = os.path.getsize(archive_file_path)
        logging.info(f"Successfully created lcov archive: {archive_file_path}")
        logging.info(f"Archive size: {final_size} bytes")
        return archive_file_path

    except Exception as e:
        logging.error(f"Failed to create lcov archive: {e}")
        raise
