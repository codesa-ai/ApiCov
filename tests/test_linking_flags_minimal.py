#!/usr/bin/env python3
"""
Minimal test script for linking flags extraction functionality.
Can be run without pytest or unittest.
"""

import sys
import os
import json
import tempfile

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.Utils import (
    extract_linking_flags,
    _parse_linking_flags_from_command,
    _extract_from_cmake_link_txt,
    _extract_from_makefile,
    _extract_makefile_variables,
    _resolve_variable_references,
    _make_paths_relative,
)


def test_parse_basic_flags():
    """Test parsing of basic linking flags"""
    print("Test: parse_basic_flags...", end=" ")
    command = "gcc -o test test.c -lstdc++ -lpthread -L/usr/lib"
    flags = _parse_linking_flags_from_command(command)
    assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
    assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
    assert "-L/usr/lib" in flags, f"Expected -L/usr/lib in {flags}"
    print("PASS")


def test_parse_wl_flags():
    """Test parsing of -Wl linker flags"""
    print("Test: parse_wl_flags...", end=" ")
    command = "g++ -o test test.cpp -Wl,--as-needed -Wl,-rpath,/opt/lib"
    flags = _parse_linking_flags_from_command(command)
    assert "-Wl,--as-needed" in flags, f"Expected -Wl,--as-needed in {flags}"
    assert "-Wl,-rpath,/opt/lib" in flags, f"Expected -Wl,-rpath,/opt/lib in {flags}"
    print("PASS")


def test_parse_space_separated():
    """Test parsing of space-separated flags"""
    print("Test: parse_space_separated...", end=" ")
    command = "gcc -o test test.c -l stdc++ -L /usr/lib"
    flags = _parse_linking_flags_from_command(command)
    assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
    assert "-L/usr/lib" in flags, f"Expected -L/usr/lib in {flags}"
    print("PASS")


def test_cmake_link_txt_extraction():
    """Test extraction from CMake link.txt files"""
    print("Test: cmake_link_txt_extraction...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CMakeFiles/target.dir/link.txt structure
        target_dir = os.path.join(tmpdir, "CMakeFiles", "myapp.dir")
        os.makedirs(target_dir)
        link_txt = os.path.join(target_dir, "link.txt")

        with open(link_txt, "w") as f:
            f.write("/usr/bin/cc -o myapp obj1.o obj2.o -lssl -lcrypto -lpthread -L/usr/lib\n")

        flags = _extract_from_cmake_link_txt(tmpdir)

        assert "-lssl" in flags, f"Expected -lssl in {flags}"
        assert "-lcrypto" in flags, f"Expected -lcrypto in {flags}"
        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
        assert "-L/usr/lib" in flags, f"Expected -L/usr/lib in {flags}"
    print("PASS")


def test_cmake_link_txt_multiple_targets():
    """Test extraction from multiple CMake link.txt files"""
    print("Test: cmake_link_txt_multiple_targets...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple targets
        for target in ["app1", "app2"]:
            target_dir = os.path.join(tmpdir, "CMakeFiles", f"{target}.dir")
            os.makedirs(target_dir)
            link_txt = os.path.join(target_dir, "link.txt")
            with open(link_txt, "w") as f:
                if target == "app1":
                    f.write("/usr/bin/cc -o app1 obj.o -lssl -lm\n")
                else:
                    f.write("/usr/bin/cc -o app2 obj.o -lcrypto -lpthread\n")

        flags = _extract_from_cmake_link_txt(tmpdir)

        # Should have flags from both targets
        assert "-lssl" in flags, f"Expected -lssl in {flags}"
        assert "-lm" in flags, f"Expected -lm in {flags}"
        assert "-lcrypto" in flags, f"Expected -lcrypto in {flags}"
        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
    print("PASS")


def test_makefile_extraction():
    """Test extraction from Makefile"""
    print("Test: makefile_extraction...", end=" ")
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("CC = gcc\n")
        f.write("LDFLAGS = -lpthread -L/usr/lib\n")
        f.write("LDLIBS = -lstdc++ -lm\n")
        f.write("\nall: test\n")
        f.flush()

        flags = _extract_from_makefile(f.name)
        os.unlink(f.name)

        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-lm" in flags, f"Expected -lm in {flags}"
        assert "-L/usr/lib" in flags, f"Expected -L/usr/lib in {flags}"
    print("PASS")


def test_makefile_multiline():
    """Test extraction of multi-line flags"""
    print("Test: makefile_multiline...", end=" ")
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("LDFLAGS = -lpthread \\\n")
        f.write("          -lstdc++ \\\n")
        f.write("          -L/usr/lib\n")
        f.flush()

        flags = _extract_from_makefile(f.name)
        os.unlink(f.name)

        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-L/usr/lib" in flags, f"Expected -L/usr/lib in {flags}"
    print("PASS")


def test_end_to_end_cmake_link_txt():
    """Test end-to-end extraction with CMake link.txt"""
    print("Test: end_to_end_cmake_link_txt...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CMakeFiles/target.dir/link.txt
        target_dir = os.path.join(tmpdir, "CMakeFiles", "myapp.dir")
        os.makedirs(target_dir)
        link_txt = os.path.join(target_dir, "link.txt")

        with open(link_txt, "w") as f:
            f.write("/usr/bin/cc -o myapp obj.o -lstdc++ -lpthread\n")

        flags = extract_linking_flags(tmpdir, "cmake", tmpdir)

        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
    print("PASS")


def test_nonexistent_build_dir():
    """Test with non-existent build directory"""
    print("Test: nonexistent_build_dir...", end=" ")
    flags = extract_linking_flags("/nonexistent/path", "cmake")
    assert flags == "", f"Expected empty string, got {flags}"
    print("PASS")


def test_deduplication():
    """Test that duplicate flags are deduplicated"""
    print("Test: deduplication...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple CMake targets with overlapping flags
        for target in ["app1", "app2", "app3"]:
            target_dir = os.path.join(tmpdir, "CMakeFiles", f"{target}.dir")
            os.makedirs(target_dir)
            link_txt = os.path.join(target_dir, "link.txt")
            with open(link_txt, "w") as f:
                # All targets have -lstdc++, creating duplicates
                f.write(f"/usr/bin/cc -o {target} obj.o -lstdc++ -lpthread -lm\n")

        flags = _extract_from_cmake_link_txt(tmpdir)

        # Count occurrences of -lstdc++
        assert flags.count("-lstdc++") == 1, (
            f"Expected 1 occurrence of -lstdc++, got {flags.count('-lstdc++')}"
        )
        assert flags.count("-lpthread") == 1, (
            f"Expected 1 occurrence of -lpthread, got {flags.count('-lpthread')}"
        )
    print("PASS")


def test_cmake_fallback_to_makefile():
    """Test fallback from cmake to Makefile when CMakeCache.txt doesn't exist"""
    print("Test: cmake_fallback_to_makefile...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        makefile_path = os.path.join(tmpdir, "Makefile")
        with open(makefile_path, "w") as f:
            f.write("LDFLAGS = -lpthread -lstdc++\n")
            f.write("LDLIBS = -lm\n")

        flags = extract_linking_flags(tmpdir, "cmake")

        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-lm" in flags, f"Expected -lm in {flags}"
    print("PASS")


def test_makefile_with_export_and_prefixes():
    """Test extraction from Makefile with export and variable prefixes (e.g., pjproject)"""
    print("Test: makefile_with_export_and_prefixes...", end=" ")
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("export APP_LDFLAGS := -L/usr/lib -pthread\n")
        f.write("export APP_LDLIBS = -lm -lstdc++\n")
        f.write("  PJ_LDFLAGS = -L/opt/lib\n")
        f.flush()

        flags = _extract_from_makefile(f.name)
        os.unlink(f.name)

        assert "-L/usr/lib" in flags, f"Expected -L/usr/lib in {flags}"
        assert "-pthread" in flags, f"Expected -pthread in {flags}"
        assert "-lm" in flags, f"Expected -lm in {flags}"
        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-L/opt/lib" in flags, f"Expected -L/opt/lib in {flags}"
    print("PASS")


def test_variable_resolution_basic():
    """Test basic variable resolution"""
    print("Test: variable_resolution_basic...", end=" ")
    variables = {
        "PREFIX": "/usr/local",
        "LIBDIR": "/opt/libs",
    }

    test_cases = [
        ("-L$(PREFIX)/lib", "-L/usr/local/lib"),
        ("-L${LIBDIR}/foo", "-L/opt/libs/foo"),
        ("-ltest", "-ltest"),
    ]

    for input_val, expected in test_cases:
        result = _resolve_variable_references(input_val, variables)
        assert result == expected, f"Expected '{expected}', got '{result}' for input '{input_val}'"

    print("PASS")


def test_variable_resolution_nested():
    """Test nested variable resolution"""
    print("Test: variable_resolution_nested...", end=" ")
    variables = {
        "PREFIX": "/usr/local",
        "LIBDIR": "$(PREFIX)/lib",
        "MYLIB": "$(LIBDIR)/mylib",
    }

    result = _resolve_variable_references("-L$(MYLIB)", variables)
    assert result == "-L/usr/local/lib/mylib", f"Expected '-L/usr/local/lib/mylib', got '{result}'"

    print("PASS")


def test_variable_resolution_unresolved():
    """Test that unresolved variables are left as-is"""
    print("Test: variable_resolution_unresolved...", end=" ")
    variables = {
        "PREFIX": "/usr/local",
    }

    result = _resolve_variable_references("-L$(PREFIX)/$(UNKNOWN_VAR)/lib", variables)
    assert result == "-L/usr/local/$(UNKNOWN_VAR)/lib", f"Expected partial resolution, got '{result}'"

    print("PASS")


def test_makefile_variable_extraction():
    """Test extraction of variables from Makefile"""
    print("Test: makefile_variable_extraction...", end=" ")
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("PREFIX = /usr/local\n")
        f.write("export LIBDIR := $(PREFIX)/lib\n")
        f.write("CFLAGS = -O2\n")
        f.write("  MYVAR = value\n")
        f.flush()

        variables = _extract_makefile_variables(f.name)
        os.unlink(f.name)

        assert "PREFIX" in variables, f"Expected PREFIX in {variables}"
        assert variables["PREFIX"] == "/usr/local", f"Wrong value for PREFIX: {variables['PREFIX']}"
        assert "LIBDIR" in variables, f"Expected LIBDIR in {variables}"
        assert variables["LIBDIR"] == "$(PREFIX)/lib", f"Wrong value for LIBDIR: {variables['LIBDIR']}"
        assert "MYVAR" in variables, f"Expected MYVAR in {variables}"

    print("PASS")


def test_makefile_extraction_with_variables():
    """Test extraction from Makefile with variable resolution"""
    print("Test: makefile_extraction_with_variables...", end=" ")
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("PREFIX = /usr/local\n")
        f.write("LIBDIR = $(PREFIX)/lib\n")
        f.write("LDFLAGS = -L$(LIBDIR) -lpthread\n")
        f.write("LDLIBS = -L$(PREFIX)/other -lm\n")
        f.flush()

        flags = _extract_from_makefile(f.name)
        os.unlink(f.name)

        assert "-L/usr/local/lib" in flags, f"Expected -L/usr/local/lib in {flags}"
        assert "-L/usr/local/other" in flags, f"Expected -L/usr/local/other in {flags}"
        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
        assert "-lm" in flags, f"Expected -lm in {flags}"

        assert "-L$(LIBDIR)" not in flags, f"Unresolved variable found in {flags}"
        assert "-L$(PREFIX)/lib" not in flags, f"Unresolved variable found in {flags}"

    print("PASS")


def test_make_paths_relative_converts_project_paths():
    """Test that project-internal absolute paths are converted to relative"""
    print("Test: make_paths_relative_converts_project_paths...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create lib directories with actual libraries
        lib_dir = os.path.join(tmpdir, "pjlib", "lib")
        os.makedirs(lib_dir)
        # Create a dummy library file
        with open(os.path.join(lib_dir, "libpj.a"), "w") as f:
            f.write("")

        flags = [
            f"-L{lib_dir}",
            "-lpj",
            "-lm",
        ]

        result = _make_paths_relative(flags, tmpdir)

        assert "-Lpjlib/lib" in result, f"Expected -Lpjlib/lib in {result}"
        assert "-lpj" in result, f"Expected -lpj in {result}"
        assert "-lm" in result, f"Expected -lm in {result}"

    print("PASS")


def test_make_paths_relative_filters_system_paths():
    """Test that system -L paths are filtered out"""
    print("Test: make_paths_relative_filters_system_paths...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        flags = [
            "-L/usr/lib",
            "-L/opt/homebrew/lib",
            "-L/usr/local/lib",
            "-lm",
            "-lpthread",
        ]

        result = _make_paths_relative(flags, tmpdir)

        assert "-L/usr/lib" not in result, f"System path should be filtered: {result}"
        assert "-L/opt/homebrew/lib" not in result, f"System path should be filtered: {result}"
        assert "-L/usr/local/lib" not in result, f"System path should be filtered: {result}"
        # System libraries should be kept
        assert "-lm" in result, f"Expected -lm in {result}"
        assert "-lpthread" in result, f"Expected -lpthread in {result}"

    print("PASS")


def test_make_paths_relative_filters_nonexistent_libs():
    """Test that libraries not found in project paths are filtered out"""
    print("Test: make_paths_relative_filters_nonexistent_libs...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create lib directory with only one library
        lib_dir = os.path.join(tmpdir, "lib")
        os.makedirs(lib_dir)
        with open(os.path.join(lib_dir, "libexists.a"), "w") as f:
            f.write("")

        flags = [
            f"-L{lib_dir}",
            "-lexists",
            "-lnonexistent",
            "-lm",  # system lib, should be kept
        ]

        result = _make_paths_relative(flags, tmpdir)

        assert "-lexists" in result, f"Expected -lexists in {result}"
        assert "-lnonexistent" not in result, f"Nonexistent lib should be filtered: {result}"
        assert "-lm" in result, f"System lib should be kept: {result}"

    print("PASS")


def test_make_paths_relative_keeps_system_libs():
    """Test that known system libraries are always kept"""
    print("Test: make_paths_relative_keeps_system_libs...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        flags = [
            "-lm",
            "-lpthread",
            "-ldl",
            "-lrt",
            "-lc",
            "-lstdc++",
            "-lssl",
            "-lcrypto",
            "-lz",
            "-lbz2",
        ]

        result = _make_paths_relative(flags, tmpdir)

        for flag in flags:
            assert flag in result, f"System lib {flag} should be kept in {result}"

    print("PASS")


def test_make_paths_relative_keeps_other_flags():
    """Test that non-path, non-library flags are preserved"""
    print("Test: make_paths_relative_keeps_other_flags...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        flags = [
            "-pthread",
            "-Wl,--as-needed",
            "-Wl,-rpath,/opt/lib",
            "-rdynamic",
        ]

        result = _make_paths_relative(flags, tmpdir)

        for flag in flags:
            assert flag in result, f"Flag {flag} should be kept in {result}"

    print("PASS")


def test_make_paths_relative_handles_shared_libs():
    """Test that shared libraries (.so, .dylib) are detected"""
    print("Test: make_paths_relative_handles_shared_libs...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        lib_dir = os.path.join(tmpdir, "lib")
        os.makedirs(lib_dir)
        # Create shared library files
        with open(os.path.join(lib_dir, "libshared.so"), "w") as f:
            f.write("")
        with open(os.path.join(lib_dir, "libmac.dylib"), "w") as f:
            f.write("")

        flags = [
            f"-L{lib_dir}",
            "-lshared",
            "-lmac",
        ]

        result = _make_paths_relative(flags, tmpdir)

        assert "-lshared" in result, f"Expected -lshared in {result}"
        assert "-lmac" in result, f"Expected -lmac in {result}"

    print("PASS")


def test_make_paths_relative_skips_nonexistent_dirs():
    """Test that -L paths to non-existent directories are filtered out"""
    print("Test: make_paths_relative_skips_nonexistent_dirs...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        flags = [
            f"-L{tmpdir}/nonexistent/lib",
            f"-L{tmpdir}/install/lib",
            "-lm",
        ]

        result = _make_paths_relative(flags, tmpdir)

        assert "-Lnonexistent/lib" not in result, f"Nonexistent dir should be filtered: {result}"
        assert "-Linstall/lib" not in result, f"Nonexistent dir should be filtered: {result}"
        assert "-lm" in result, f"System lib should be kept: {result}"

    print("PASS")


def test_end_to_end_with_library_validation():
    """Test end-to-end extraction with library existence validation"""
    print("Test: end_to_end_with_library_validation...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create lib directory structure
        lib_dir = os.path.join(tmpdir, "mylib", "lib")
        os.makedirs(lib_dir)
        with open(os.path.join(lib_dir, "libmylib.a"), "w") as f:
            f.write("")

        # Create Makefile with both existing and non-existing libs
        makefile_path = os.path.join(tmpdir, "Makefile")
        with open(makefile_path, "w") as f:
            f.write(f"LDFLAGS = -L{lib_dir} -L/usr/lib\n")
            f.write("LDLIBS = -lmylib -lnonexistent -lm -lpthread\n")

        flags = extract_linking_flags(tmpdir, "make", tmpdir)

        assert "-Lmylib/lib" in flags, f"Expected -Lmylib/lib in {flags}"
        assert "-L/usr/lib" not in flags, f"System path should be filtered: {flags}"
        assert "-lmylib" in flags, f"Expected -lmylib in {flags}"
        assert "-lnonexistent" not in flags, f"Nonexistent lib should be filtered: {flags}"
        assert "-lm" in flags, f"System lib should be kept: {flags}"
        assert "-lpthread" in flags, f"System lib should be kept: {flags}"

    print("PASS")


def main():
    print("=" * 60)
    print("Running Linking Flags Extraction Tests")
    print("=" * 60)
    print()

    tests = [
        test_parse_basic_flags,
        test_parse_wl_flags,
        test_parse_space_separated,
        # CMake link.txt tests
        test_cmake_link_txt_extraction,
        test_cmake_link_txt_multiple_targets,
        test_end_to_end_cmake_link_txt,
        # Makefile tests
        test_makefile_extraction,
        test_makefile_multiline,
        test_nonexistent_build_dir,
        test_deduplication,
        test_cmake_fallback_to_makefile,
        test_makefile_with_export_and_prefixes,
        test_variable_resolution_basic,
        test_variable_resolution_nested,
        test_variable_resolution_unresolved,
        test_makefile_variable_extraction,
        test_makefile_extraction_with_variables,
        # Path relative and library validation tests
        test_make_paths_relative_converts_project_paths,
        test_make_paths_relative_filters_system_paths,
        test_make_paths_relative_filters_nonexistent_libs,
        test_make_paths_relative_keeps_system_libs,
        test_make_paths_relative_keeps_other_flags,
        test_make_paths_relative_handles_shared_libs,
        test_make_paths_relative_skips_nonexistent_dirs,
        test_end_to_end_with_library_validation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
