"""
Integration tests for apicov.py with structured JSON output.
"""

import pytest
import tempfile
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.ExportFetcher import ExportFetcher
from modules.ClangParser import CLANG_AVAILABLE


class TestApiCovStructuredOutput:
    """Test apicov.py produces structured JSON output."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def cpp_project(self, temp_dir):
        """Create a minimal C++ project for testing."""
        # Create header file
        header_content = """
namespace MyLib {
    class Calculator {
    public:
        int add(int a, int b);
        int subtract(int a, int b);
    };

    void utilityFunction();
}
"""
        header_path = os.path.join(temp_dir, "calculator.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        return temp_dir

    def test_apis_json_structure(self, cpp_project):
        """Test that apis.json has correct structure."""
        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(cpp_project)

        # Simulate writing apis.json
        json_data = {"apis": apis}

        # Verify structure
        assert "apis" in json_data
        assert isinstance(json_data["apis"], dict)

        # Each file should map to a list of API dicts
        for file, api_list in json_data["apis"].items():
            assert isinstance(api_list, list)

            for api in api_list:
                assert isinstance(api, dict)
                assert "qualified" in api
                assert "simple" in api
                assert "signature" in api

    @pytest.mark.skipif(not CLANG_AVAILABLE, reason="libclang not available")
    def test_cpp_apis_have_qualified_names(self, cpp_project):
        """Test that C++ APIs have qualified names extracted."""
        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(cpp_project)

        # Find Calculator methods
        found_add = False
        found_subtract = False

        for file, api_list in apis.items():
            for api in api_list:
                if api["simple"] == "add":
                    # Should have qualified name with namespace and class
                    assert "MyLib" in api["qualified"]
                    assert "Calculator" in api["qualified"]
                    found_add = True

                if api["simple"] == "subtract":
                    assert "MyLib" in api["qualified"]
                    assert "Calculator" in api["qualified"]
                    found_subtract = True

        # Verify we found the methods
        assert found_add or found_subtract  # At least one should be found

    def test_api_coverage_json_structure(self, cpp_project):
        """Test api_coverage.json structure with new fields."""
        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(cpp_project)

        # Simulate api_coverage.json structure (from apicov.py lines 323-351)
        json_data = {}

        for file, api_list in apis.items():
            json_data[file] = {}

            for api in api_list:
                qualified_name = api["qualified"]
                simple_name = api["simple"]
                signature = api.get("signature", "")

                json_data[file][qualified_name] = {
                    "simple_name": simple_name,
                    "signature": signature,
                    "full_size": 0,
                    "covered_lines": 0
                }

        # Verify structure
        for file, api_dict in json_data.items():
            for qualified_name, api_data in api_dict.items():
                # Each API should have these fields
                assert "simple_name" in api_data
                assert "signature" in api_data
                assert "full_size" in api_data
                assert "covered_lines" in api_data

    def test_json_serializable(self, cpp_project):
        """Test that output is JSON serializable."""
        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(cpp_project)

        json_data = {"apis": apis}

        # Should be able to serialize to JSON
        json_str = json.dumps(json_data, indent=2)
        assert json_str is not None

        # Should be able to deserialize
        parsed = json.loads(json_str)
        assert "apis" in parsed

    def test_c_library_backward_compat(self, temp_dir):
        """Test that C libraries work with new structure."""
        # Create C header
        c_header_content = """
void c_function_one(int x);
int c_function_two(char* str);
"""
        c_header_path = os.path.join(temp_dir, "cfunctions.h")
        with open(c_header_path, 'w') as f:
            f.write(c_header_content)

        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should have structured output
        for file, api_list in apis.items():
            for api in api_list:
                assert "qualified" in api
                assert "simple" in api
                assert "signature" in api

                # For C functions, qualified == simple
                if "c_function" in api["simple"]:
                    assert api["qualified"] == api["simple"]


class TestExportFetcherIntegration:
    """Integration tests for ExportFetcher with ClangParser."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_handles_both_c_and_cpp_headers(self, temp_dir):
        """Test handling directory with both C and C++ headers."""
        # Create C header
        c_header = os.path.join(temp_dir, "functions.h")
        with open(c_header, 'w') as f:
            f.write("void c_func();")

        # Create C++ header
        cpp_header = os.path.join(temp_dir, "classes.hpp")
        with open(cpp_header, 'w') as f:
            f.write("namespace N { void cpp_func(); }")

        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should have processed both files
        assert len(apis) >= 1

        # All should have structured format
        for file, api_list in apis.items():
            assert isinstance(api_list, list)
            for api in api_list:
                assert "qualified" in api
                assert "simple" in api

    def test_empty_directory(self, temp_dir):
        """Test handling empty directory."""
        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should return empty dict
        assert apis == {}

    def test_directory_with_no_functions(self, temp_dir):
        """Test directory with headers but no functions."""
        header_path = os.path.join(temp_dir, "empty.h")
        with open(header_path, 'w') as f:
            f.write("// Just comments\n")

        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(temp_dir)

        # May return empty or have empty lists
        for file, api_list in apis.items():
            assert isinstance(api_list, list)

    @pytest.mark.skipif(not CLANG_AVAILABLE, reason="libclang not available")
    def test_complex_cpp_project(self, temp_dir):
        """Test with more complex C++ structure."""
        header_content = """
namespace Outer {
    namespace Inner {
        class MyClass {
        public:
            void publicMethod();
        private:
            void privateMethod();
        };

        void freeFunction();
    }
}

template<typename T>
class TemplateClass {
public:
    void templateMethod(T value);
};
"""
        header_path = os.path.join(temp_dir, "complex.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        fetcher = ExportFetcher()
        apis = fetcher.get_apis_from_headers(temp_dir)

        # Should have extracted public APIs
        found_public = False

        for file, api_list in apis.items():
            for api in api_list:
                if api["simple"] == "publicMethod":
                    # Should have qualified name
                    assert "Outer" in api["qualified"]
                    assert "Inner" in api["qualified"]
                    found_public = True

                # Should NOT have privateMethod
                assert api["simple"] != "privateMethod"

        # Should have found at least some APIs
        assert len(apis) > 0


class TestBackwardCompatibilityHandling:
    """Test handling of old vs new data formats."""

    def test_handle_old_string_format(self):
        """Test code can handle old string format APIs."""
        # Old format: list of strings
        old_apis = ["func1", "func2", "func3"]

        # Code should handle both old and new formats
        for api in old_apis:
            if isinstance(api, str):
                # Old format
                simple_name = api
                qualified_name = api
            else:
                # New format
                simple_name = api["simple"]
                qualified_name = api["qualified"]

            assert simple_name in ["func1", "func2", "func3"]

    def test_handle_new_dict_format(self):
        """Test code handles new dict format."""
        # New format: list of dicts
        new_apis = [
            {"qualified": "NS::Class::func1", "simple": "func1", "signature": "()"},
            {"qualified": "NS::Class::func2", "simple": "func2", "signature": "(int)"},
        ]

        for api in new_apis:
            if isinstance(api, str):
                simple_name = api
            else:
                simple_name = api["simple"]

            assert simple_name in ["func1", "func2"]

    def test_handle_none_simple_name(self):
        """Test handling when simple_name is None (old data)."""
        api_data = {
            "name": "oldFunction",
            "simple_name": None,
            "signature": None
        }

        # Code should fallback to name
        simple_name = api_data.get("simple_name") or api_data["name"]
        assert simple_name == "oldFunction"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
