import json
import os
import re
import shlex
import subprocess
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
        logging.error(f"ERROR: Info file does not exist: {info_file}")
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
        logging.error(f"ERROR: Failed to create lcov archive: {e}")
        raise


def extract_linking_flags(build_dir: str, build_system: str) -> str:
    """
    Extracts linking flags from the build directory using a hybrid strategy.

    Strategy:
    1. Try compile_commands.json (works for CMake and Meson)
    2. Try build system introspection (cmake --system-information, meson introspect)
    3. Fall back to parsing build files directly

    Args:
        build_dir (str): Path to the build directory
        build_system (str): Build system type ('cmake', 'meson', 'make', 'ninja', 'unknown')

    Returns:
        str: Space-separated linking flags (e.g., '-lstdc++ -lpthread -L/usr/lib') or empty string
    """
    if not os.path.isdir(build_dir):
        logging.warning(f"Build directory does not exist: {build_dir}")
        return ""

    logging.info(f"Extracting linking flags from {build_dir} (build system: {build_system})")

    # Try compile_commands.json
    compile_commands_path = os.path.join(build_dir, "compile_commands.json")
    if os.path.exists(compile_commands_path):
        logging.debug("DEBUG: Found compile_commands.json, attempting to extract flags")
        flags = _extract_from_compile_commands(compile_commands_path)
        if flags:
            logging.info(f"Extracted {len(flags)} unique linking flags from compile_commands.json")
            return ' '.join(flags)

    # Build system introspection
    if build_system == "cmake":
        logging.debug("DEBUG: Attempting to extract from CMakeCache.txt")
        flags = _extract_from_cmake_cache(build_dir)
        if flags:
            logging.info(f"Extracted {len(flags)} unique linking flags from CMake cache")
            return ' '.join(flags)
        logging.debug("DEBUG: No flags found in CMakeCache.txt")
    elif build_system == "meson":
        logging.debug("DEBUG: Attempting meson introspection")
        flags = _extract_from_meson_introspection(build_dir)
        if flags:
            logging.info(f"Extracted {len(flags)} unique linking flags from Meson introspection")
            return ' '.join(flags)
        logging.debug("DEBUG: Meson introspection yielded no flags")

    # Direct build file parsing
    if build_system == "make":
        makefile_path = _find_makefile(build_dir)
        if makefile_path:
            flags = _extract_from_makefile(makefile_path)
        else:
            flags = []
    else:
        flags = []

    # Fallback: If no flags found yet, try Makefile extraction regardless of detected build system
    # This handles cases where projects have multiple build systems (e.g., both CMakeLists.txt and Makefile)
    if not flags and build_system != "make":
        logging.debug("DEBUG: Primary extraction failed, trying Makefile as fallback")
        makefile_path = _find_makefile(build_dir)
        if makefile_path:
            flags = _extract_from_makefile(makefile_path)
            if flags:
                logging.info(f"Extracted {len(flags)} unique linking flags from Makefile (fallback)")

    if flags:
        logging.info(f"Extracted {len(flags)} unique linking flags from {build_system} build files")
        return ' '.join(flags)
    else:
        logging.warning(f"No linking flags found in {build_dir}")
        return ""


def _extract_from_compile_commands(compile_commands_path: str) -> list[str]:
    """
    Extracts linking flags from compile_commands.json.

    Args:
        compile_commands_path (str): Path to compile_commands.json

    Returns:
        list[str]: Deduplicated list of linking flags
    """
    try:
        with open(compile_commands_path, 'r') as f:
            commands = json.load(f)

        all_flags = set()

        for entry in commands:
            command = entry.get('command', '')
            if not command:
                # Some entries use 'arguments' instead of 'command'
                arguments = entry.get('arguments', [])
                if arguments:
                    command = ' '.join(arguments)

            flags = _parse_linking_flags_from_command(command)
            all_flags.update(flags)

        return sorted(list(all_flags))

    except Exception as e:
        logging.error(f"ERROR: Failed to parse compile_commands.json: {e}")
        return []


def _parse_linking_flags_from_command(command: str) -> list[str]:
    """
    Parses linking flags from a compiler/linker command string.

    Extracts:
    - Library names: -l<name>
    - Library paths: -L<path>
    - Linker flags: -Wl,<options>
    - Other common flags: -pthread, -ldl, etc.

    Args:
        command (str): Full compiler/linker command string

    Returns:
        list[str]: List of linking flags
    """
    flags = []

    try:
        # Split command respecting quotes and escapes
        tokens = shlex.split(command)
    except ValueError:
        # If shlex fails, fall back to simple split
        tokens = command.split()

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Match -l<library> (library names)
        if token.startswith('-l'):
            if len(token) > 2:
                flags.append(token)
            elif i + 1 < len(tokens):
                # Handle -l <library> (space-separated)
                flags.append(f"-l{tokens[i + 1]}")
                i += 1

        # Match -L<path> (library paths)
        elif token.startswith('-L'):
            if len(token) > 2:
                flags.append(token)
            elif i + 1 < len(tokens):
                # Handle -L <path> (space-separated)
                flags.append(f"-L{tokens[i + 1]}")
                i += 1

        # Match -Wl,<options> (linker options)
        elif token.startswith('-Wl,'):
            flags.append(token)

        # Match other common linking flags
        elif token in ['-pthread', '-ldl', '-lm', '-lrt', '-static', '-shared', '-rdynamic']:
            flags.append(token)

        i += 1

    return flags


def _extract_from_cmake_cache(build_dir: str) -> list[str]:
    """
    Extracts linking flags from CMakeCache.txt.

    Args:
        build_dir (str): Path to CMake build directory

    Returns:
        list[str]: List of linking flags
    """
    cache_path = os.path.join(build_dir, "CMakeCache.txt")
    if not os.path.exists(cache_path):
        logging.debug("DEBUG: CMakeCache.txt not found")
        return []

    all_flags = set()

    try:
        with open(cache_path, 'r') as f:
            for line in f:
                line = line.strip()

                # Look for linker flag variables
                if any(keyword in line for keyword in [
                    'CMAKE_EXE_LINKER_FLAGS',
                    'CMAKE_SHARED_LINKER_FLAGS',
                    'CMAKE_MODULE_LINKER_FLAGS',
                    'CMAKE_STATIC_LINKER_FLAGS',
                    'LINK_LIBRARIES',
                    'INTERFACE_LINK_LIBRARIES'
                ]):
                    # Extract value after '='
                    if '=' in line and not line.startswith('//'):
                        value = line.split('=', 1)[1]
                        flags = _parse_linking_flags_from_command(value)
                        all_flags.update(flags)

        return sorted(list(all_flags))

    except Exception as e:
        logging.error(f"ERROR: Failed to parse CMakeCache.txt: {e}")
        return []


def _extract_from_meson_introspection(build_dir: str) -> list[str]:
    """
    Extracts linking flags using meson introspect commands.

    Args:
        build_dir (str): Path to Meson build directory

    Returns:
        list[str]: List of linking flags
    """
    all_flags = set()

    try:
        # Run meson introspect --targets
        result = subprocess.run(
            ['meson', 'introspect', '--targets', build_dir],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            targets = json.loads(result.stdout)

            for target in targets:
                # Extract link flags from target
                if 'link_args' in target:
                    for arg in target['link_args']:
                        if isinstance(arg, str):
                            flags = _parse_linking_flags_from_command(arg)
                            all_flags.update(flags)

                # Extract dependencies
                if 'dependencies' in target:
                    for dep in target['dependencies']:
                        if isinstance(dep, str) and dep.startswith('-l'):
                            all_flags.add(dep)

        # Also try --buildoptions for global link flags
        result = subprocess.run(
            ['meson', 'introspect', '--buildoptions', build_dir],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            options = json.loads(result.stdout)

            for option in options:
                if 'link' in option.get('name', '').lower():
                    value = option.get('value', '')
                    if isinstance(value, str):
                        flags = _parse_linking_flags_from_command(value)
                        all_flags.update(flags)

        return sorted(list(all_flags))

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        logging.debug(f"DEBUG: Meson introspection failed: {e}")
        return []
    except Exception as e:
        logging.error(f"ERROR: Failed to introspect Meson build: {e}")
        return []


def _find_makefile(build_dir: str) -> str | None:
    """
    Finds Makefile or build.mak in build_dir or parent directories.

    Args:
        build_dir (str): Starting directory

    Returns:
        str | None: Path to Makefile/build.mak or None if not found
    """
    current = os.path.abspath(build_dir)

    # Search up to 3 levels up
    for _ in range(3):
        # Check for common makefile names (prefer build.mak over Makefile if both exist)
        for makefile_name in ["build.mak", "Makefile"]:
            makefile = os.path.join(current, makefile_name)
            if os.path.exists(makefile):
                return makefile

        parent = os.path.dirname(current)
        if parent == current:  # Reached root
            break
        current = parent

    return None


def _extract_makefile_variables(makefile_path: str) -> dict[str, str]:
    """
    Extracts all variable definitions from a Makefile.

    Args:
        makefile_path (str): Path to Makefile

    Returns:
        dict[str, str]: Dictionary mapping variable names to their values
    """
    variables = {}

    try:
        with open(makefile_path, 'r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()

            match = re.match(r'^\s*(?:export\s+)?(\w+)\s*[:+]?=\s*(.*)$', line)
            if match:
                var_name = match.group(1)
                var_value = match.group(2)

                while var_value.endswith('\\') and i + 1 < len(lines):
                    i += 1
                    var_value = var_value[:-1] + ' ' + lines[i].strip()

                variables[var_name] = var_value.strip()

            i += 1

        return variables

    except Exception as e:
        logging.debug(f"DEBUG: Failed to extract Makefile variables: {e}")
        return {}


def _resolve_variable_references(text: str, variables: dict[str, str], max_iterations: int = 10) -> str:
    """
    Resolves variable references in text using environment and Makefile variables.

    Handles:
    - $(VAR) and ${VAR} syntax
    - Nested variables (e.g., $(PREFIX)/$(SUBDIR))
    - Recursive expansion (e.g., A=$(B), B=$(C), C=value)

    Args:
        text (str): Text containing variable references
        variables (dict): Makefile variables
        max_iterations (int): Maximum recursion depth to prevent infinite loops

    Returns:
        str: Text with variables resolved (unresolved vars left as-is)
    """
    if not text:
        return text

    for _ in range(max_iterations):
        original = text

        var_refs = re.findall(r'\$\((\w+)\)|\$\{(\w+)\}', text)

        if not var_refs:
            break

        for var_ref in var_refs:
            var_name = var_ref[0] or var_ref[1]

            value = os.environ.get(var_name)

            if value is None:
                value = variables.get(var_name)

            if value is not None:
                text = text.replace(f'$({var_name})', value)
                text = text.replace(f'${{{var_name}}}', value)

        if text == original:
            break

    return text


def _extract_from_makefile(makefile_path: str) -> list[str]:
    """
    Extracts linking flags from Makefile.

    Args:
        makefile_path (str): Path to Makefile

    Returns:
        list[str]: List of linking flags (with variables resolved where possible)
    """
    all_flags = set()

    try:
        makefile_vars = _extract_makefile_variables(makefile_path)

        with open(makefile_path, 'r') as f:
            content = f.read()

        var_pattern = r'^\s*(?:export\s+)?(?:\w+_)?(LDFLAGS|LDLIBS|LIBS|LINKFLAGS)\s*[:\+]?=\s*(.*)$'

        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            match = re.match(var_pattern, line)
            if match:
                var_value = match.group(2)

                # Handle line continuations
                while var_value.endswith('\\') and i + 1 < len(lines):
                    var_value = var_value[:-1] + ' ' + lines[i + 1].strip()
                    i += 1

                # Parse flags from value
                flags = _parse_linking_flags_from_command(var_value)
                all_flags.update(flags)

            i += 1

        resolved_flags = set()
        for flag in all_flags:
            resolved_flag = _resolve_variable_references(flag, makefile_vars)
            resolved_flags.add(resolved_flag)

        return sorted(list(resolved_flags))

    except Exception as e:
        logging.error(f"ERROR: Failed to parse Makefile: {e}")
        return []
