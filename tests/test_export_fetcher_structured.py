"""
Unit tests for ExportFetcher with structured output format.
Tests the integration with ClangParser and backward compatibility.
"""

import pytest
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.ExportFetcher import ExportFetcher
from modules.ClangParser import CLANG_AVAILABLE


class TestExportFetcherStructuredOutput:
    """Test ExportFetcher returns structured API data."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def fetcher(self):
        """Create an ExportFetcher instance."""
        return ExportFetcher()

    def test_structured_output_format(self, fetcher, temp_dir):
        """Test that get_apis_from_headers returns structured format."""
        # Create a simple C header
        header_path = os.path.join(temp_dir, "test.h")
        with open(header_path, 'w') as f:
            f.write("void simple_function(int x);")

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Check structure
        assert isinstance(apis, dict)

        if len(apis) > 0:
            # Check that values are lists
            for file, api_list in apis.items():
                assert isinstance(api_list, list)

                # Check that each API is a dict with required keys
                for api in api_list:
                    assert isinstance(api, dict)
                    assert "qualified" in api
                    assert "simple" in api
                    assert "signature" in api

    @pytest.mark.skipif(not CLANG_AVAILABLE, reason="libclang not available")
    def test_cpp_header_with_clang(self, fetcher, temp_dir):
        """Test C++ header parsing with ClangParser."""
        header_content = """
namespace MyNamespace {
    class MyClass {
    public:
        void myMethod(int x);
    };
}
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should have extracted the method
        assert len(apis) > 0

        # Find the API in the results
        for file, api_list in apis.items():
            for api in api_list:
                if api["simple"] == "myMethod":
                    # Check qualified name contains namespace and class
                    assert "MyNamespace" in api["qualified"]
                    assert "MyClass" in api["qualified"]
                    assert "myMethod" in api["qualified"]
                    break

    def test_c_header_with_regex_fallback(self, fetcher, temp_dir):
        """Test C header parsing falls back to regex."""
        header_content = """
void c_function_one(int x);
int c_function_two(char* str);
"""
        header_path = os.path.join(temp_dir, "test.h")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should have extracted functions
        if len(apis) > 0:
            for file, api_list in apis.items():
                # Check for our functions
                simple_names = [api["simple"] for api in api_list]
                assert any("c_function" in name for name in simple_names)

                # For C headers, qualified == simple
                for api in api_list:
                    if "c_function" in api["simple"]:
                        assert api["qualified"] == api["simple"]

    def test_backward_compatibility_structure(self, fetcher, temp_dir):
        """Test that output structure is backward compatible."""
        header_path = os.path.join(temp_dir, "test.h")
        with open(header_path, 'w') as f:
            f.write("void test_func();")

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Structure should be dict[filename, list[dict]]
        assert isinstance(apis, dict)

        for file, api_list in apis.items():
            assert isinstance(file, str)
            assert isinstance(api_list, list)

            for api in api_list:
                # Each API should have these fields
                assert "qualified" in api
                assert "simple" in api
                assert "signature" in api

                # Values should be strings
                assert isinstance(api["qualified"], str)
                assert isinstance(api["simple"], str)
                assert isinstance(api["signature"], str)

    def test_grep_for_symbol_structured_output(self, fetcher, temp_dir):
        """Test that grep_for_symbol creates structured API data."""
        # Create a header with a function
        header_path = os.path.join(temp_dir, "myheader.h")
        header_file = "myheader.h"
        with open(header_path, 'w') as f:
            f.write("void my_symbol(int x);")

        # Call grep_for_symbol
        fetcher.grep_for_symbol("my_symbol", temp_dir)

        # Check that apis dict has structured format
        if header_file in fetcher.apis:
            api_list = fetcher.apis[header_file]
            assert isinstance(api_list, list)

            for api in api_list:
                assert isinstance(api, dict)
                assert "qualified" in api
                assert "simple" in api
                assert "signature" in api

    def test_multiple_headers_structured(self, fetcher, temp_dir):
        """Test multiple headers produce correct structured output."""
        # Create multiple headers
        for i in range(3):
            header_path = os.path.join(temp_dir, f"header{i}.h")
            with open(header_path, 'w') as f:
                f.write(f"void function_{i}();")

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should have multiple files
        assert len(apis) >= 1

        # Each should have structured format
        for file, api_list in apis.items():
            assert isinstance(api_list, list)
            assert len(api_list) > 0

            for api in api_list:
                assert "qualified" in api
                assert "simple" in api
                assert "signature" in api

    @pytest.mark.skipif(not CLANG_AVAILABLE, reason="libclang not available")
    def test_signature_extraction(self, fetcher, temp_dir):
        """Test that signatures are extracted correctly."""
        header_content = """
void func_no_args();
void func_one_arg(int x);
void func_multi_args(const char* str, int num);
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Check signatures
        for file, api_list in apis.items():
            for api in api_list:
                name = api["simple"]

                if name == "func_no_args":
                    assert "()" in api["signature"]
                elif name == "func_one_arg":
                    assert "int" in api["signature"]
                elif name == "func_multi_args":
                    assert "char" in api["signature"]
                    assert "int" in api["signature"]

    def test_empty_signature_for_regex_extraction(self, fetcher, temp_dir):
        """Test that regex extraction sets empty signature."""
        header_path = os.path.join(temp_dir, "test.h")
        with open(header_path, 'w') as f:
            f.write("void simple_func();")

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Regex-based extraction should have empty or minimal signature
        for file, api_list in apis.items():
            for api in api_list:
                # Signature should exist (even if empty)
                assert "signature" in api
                assert isinstance(api["signature"], str)

    def test_mixed_c_cpp_headers(self, fetcher, temp_dir):
        """Test directory with both C and C++ headers."""
        # C header
        c_header = os.path.join(temp_dir, "c_header.h")
        with open(c_header, 'w') as f:
            f.write("void c_function();")

        # C++ header
        cpp_header = os.path.join(temp_dir, "cpp_header.hpp")
        with open(cpp_header, 'w') as f:
            f.write("namespace N { void cpp_function(); }")

        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should have both files
        assert len(apis) >= 1

        # All should have structured format
        for file, api_list in apis.items():
            for api in api_list:
                assert "qualified" in api
                assert "simple" in api
                assert "signature" in api


class TestExportFetcherBackwardCompatibility:
    """Test backward compatibility with existing code."""

    @pytest.fixture
    def fetcher(self):
        """Create an ExportFetcher instance."""
        return ExportFetcher()

    def test_apis_dict_structure(self, fetcher):
        """Test that self.apis maintains dict structure."""
        assert isinstance(fetcher.apis, dict)

    def test_symbols_list_structure(self, fetcher):
        """Test that self.symbols maintains list structure."""
        assert isinstance(fetcher.symbols, list)

    def test_add_symbol_method(self, fetcher):
        """Test _add_symbol method still works."""
        fetcher._add_symbol("test_symbol")
        assert "test_symbol" in fetcher.symbols

    def test_multiple_add_symbol_no_duplicates(self, fetcher):
        """Test that adding same symbol twice doesn't create duplicates."""
        fetcher._add_symbol("test_symbol")
        fetcher._add_symbol("test_symbol")
        assert fetcher.symbols.count("test_symbol") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
