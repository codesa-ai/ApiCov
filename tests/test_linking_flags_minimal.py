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
    _extract_from_compile_commands,
    _extract_from_cmake_cache,
    _extract_from_makefile,
    _extract_makefile_variables,
    _resolve_variable_references,
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


def test_compile_commands_extraction():
    """Test extraction from compile_commands.json"""
    print("Test: compile_commands_extraction...", end=" ")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        compile_commands = [
            {"command": "gcc -o test.o test.c -lstdc++ -lpthread", "file": "test.c"},
            {"command": "g++ -o main.o main.cpp -lm -L/opt/lib", "file": "main.cpp"},
        ]
        json.dump(compile_commands, f)
        f.flush()

        flags = _extract_from_compile_commands(f.name)
        os.unlink(f.name)

        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
        assert "-lm" in flags, f"Expected -lm in {flags}"
        assert "-L/opt/lib" in flags, f"Expected -L/opt/lib in {flags}"
    print("PASS")


def test_cmake_cache_extraction():
    """Test extraction from CMakeCache.txt"""
    print("Test: cmake_cache_extraction...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "CMakeCache.txt")

        with open(cache_file, "w") as f:
            f.write("# CMake cache\n")
            f.write("CMAKE_EXE_LINKER_FLAGS:STRING=-lpthread -lstdc++\n")
            f.write("CMAKE_SHARED_LINKER_FLAGS:STRING=-L/usr/lib -lm\n")

        flags = _extract_from_cmake_cache(tmpdir)

        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-lm" in flags, f"Expected -lm in {flags}"
        assert "-L/usr/lib" in flags, f"Expected -L/usr/lib in {flags}"
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


def test_end_to_end_with_compile_commands():
    """Test end-to-end extraction with compile_commands.json"""
    print("Test: end_to_end_with_compile_commands...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        compile_commands_file = os.path.join(tmpdir, "compile_commands.json")

        with open(compile_commands_file, "w") as f:
            json.dump(
                [{"command": "gcc test.c -lstdc++ -lpthread", "file": "test.c"}], f
            )

        flags = extract_linking_flags(tmpdir, "cmake")

        assert "-lstdc++" in flags, f"Expected -lstdc++ in {flags}"
        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
    print("PASS")


def test_end_to_end_with_cmake_cache():
    """Test end-to-end extraction with CMakeCache.txt"""
    print("Test: end_to_end_with_cmake_cache...", end=" ")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "CMakeCache.txt")

        with open(cache_file, "w") as f:
            f.write("CMAKE_EXE_LINKER_FLAGS:STRING=-lpthread\n")

        flags = extract_linking_flags(tmpdir, "cmake")

        assert "-lpthread" in flags, f"Expected -lpthread in {flags}"
    print("PASS")


def test_nonexistent_build_dir():
    """Test with non-existent build directory"""
    print("Test: nonexistent_build_dir...", end=" ")
    flags = extract_linking_flags("/nonexistent/path", "cmake")
    assert flags == [], f"Expected empty list, got {flags}"
    print("PASS")


def test_deduplication():
    """Test that duplicate flags are deduplicated"""
    print("Test: deduplication...", end=" ")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        compile_commands = [
            {"command": "gcc test1.c -lstdc++ -lpthread", "file": "test1.c"},
            {"command": "gcc test2.c -lstdc++ -lm", "file": "test2.c"},
        ]
        json.dump(compile_commands, f)
        f.flush()

        flags = _extract_from_compile_commands(f.name)
        os.unlink(f.name)

        # Count occurrences of -lstdc++
        assert flags.count("-lstdc++") == 1, (
            f"Expected 1 occurrence of -lstdc++, got {flags.count('-lstdc++')}"
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


def main():
    print("=" * 60)
    print("Running Linking Flags Extraction Tests")
    print("=" * 60)
    print()

    tests = [
        test_parse_basic_flags,
        test_parse_wl_flags,
        test_parse_space_separated,
        test_compile_commands_extraction,
        test_cmake_cache_extraction,
        test_makefile_extraction,
        test_makefile_multiline,
        test_end_to_end_with_compile_commands,
        test_end_to_end_with_cmake_cache,
        test_nonexistent_build_dir,
        test_deduplication,
        test_cmake_fallback_to_makefile,
        test_makefile_with_export_and_prefixes,
        test_variable_resolution_basic,
        test_variable_resolution_nested,
        test_variable_resolution_unresolved,
        test_makefile_variable_extraction,
        test_makefile_extraction_with_variables,
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
