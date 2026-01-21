"""
Unit tests for Coverage.py module, specifically the updated _extract_function_name method.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.Coverage import LibCoverage


class TestExtractFunctionName:
    """Test the _extract_function_name method that returns (qualified, simple) tuples."""

    @pytest.fixture
    def coverage(self, tmp_path):
        """Create a LibCoverage instance for testing."""
        # Create with minimal setup
        return LibCoverage([], str(tmp_path))

    def test_plain_c_function(self, coverage):
        """Test plain C function names pass through unchanged."""
        qualified, simple = coverage._extract_function_name("my_function")
        assert qualified == "my_function"
        assert simple == "my_function"

    def test_c_function_with_underscores(self, coverage):
        """Test C function with underscores."""
        qualified, simple = coverage._extract_function_name("SDL_Init")
        assert qualified == "SDL_Init"
        assert simple == "SDL_Init"

    def test_cpp_simple_qualified_name(self, coverage):
        """Test simple C++ qualified name namespace::function."""
        qualified, simple = coverage._extract_function_name("MyNamespace::myFunction()")
        assert qualified == "MyNamespace::myFunction"
        assert simple == "myFunction"

    def test_cpp_class_method(self, coverage):
        """Test C++ class method."""
        qualified, simple = coverage._extract_function_name("MyClass::myMethod()")
        assert qualified == "MyClass::myMethod"
        assert simple == "myMethod"

    def test_cpp_namespace_class_method(self, coverage):
        """Test C++ method with namespace and class."""
        qualified, simple = coverage._extract_function_name(
            "lok::Document::saveAs(char const*, char const*)"
        )
        assert qualified == "lok::Document::saveAs"
        assert simple == "saveAs"

    def test_cpp_nested_namespace(self, coverage):
        """Test nested namespace."""
        qualified, simple = coverage._extract_function_name(
            "Outer::Inner::Deep::function()"
        )
        assert qualified == "Outer::Inner::Deep::function"
        assert simple == "function"

    def test_cpp_template_erased(self, coverage):
        """Test template parameters are erased."""
        qualified, simple = coverage._extract_function_name(
            "std::vector<int>::push_back(int)"
        )
        assert qualified == "std::vector::push_back"
        assert simple == "push_back"

    def test_cpp_complex_template(self, coverage):
        """Test complex template parameters."""
        qualified, simple = coverage._extract_function_name(
            "MyClass<std::string, int>::method<double>()"
        )
        # Template parameters should be erased
        assert "::" in qualified
        assert simple == "method"

    def test_cpp_operator_overload(self, coverage):
        """Test operator overload."""
        qualified, simple = coverage._extract_function_name(
            "MyClass::operator<<(std::ostream&)"
        )
        # Should preserve operator
        assert "operator<<" in simple
        assert qualified == "MyClass::operator<<"

    def test_cpp_operator_plus(self, coverage):
        """Test operator+ overload."""
        qualified, simple = coverage._extract_function_name(
            "String::operator+(const String&)"
        )
        assert simple == "operator+"
        assert qualified == "String::operator+"

    def test_no_parameters(self, coverage):
        """Test function without parentheses."""
        qualified, simple = coverage._extract_function_name("namespace::Class::method")
        assert qualified == "namespace::Class::method"
        assert simple == "method"

    def test_const_char_pointer_params(self, coverage):
        """Test parameters with const char*."""
        qualified, simple = coverage._extract_function_name(
            "MyClass::func(char const*, char const*, char const*)"
        )
        assert qualified == "MyClass::func"
        assert simple == "func"

    def test_reference_params(self, coverage):
        """Test parameters with references."""
        qualified, simple = coverage._extract_function_name(
            "MyClass::func(const std::string&, int&)"
        )
        assert qualified == "MyClass::func"
        assert simple == "func"

    def test_pointer_params(self, coverage):
        """Test parameters with pointers."""
        qualified, simple = coverage._extract_function_name(
            "MyClass::func(int*, char**, void*)"
        )
        assert qualified == "MyClass::func"
        assert simple == "func"

    def test_whitespace_variations(self, coverage):
        """Test different whitespace patterns."""
        # Extra spaces
        qualified, simple = coverage._extract_function_name(
            "  MyClass :: method  (  int  )  "
        )
        # Should handle gracefully (may strip whitespace)
        assert "method" in simple

    def test_anonymous_namespace(self, coverage):
        """Test anonymous namespace (represented as empty in demangled output)."""
        # Anonymous namespaces might appear in various forms
        qualified, simple = coverage._extract_function_name(
            "(anonymous namespace)::function()"
        )
        assert qualified == "(anonymous namespace)::function"
        assert simple == "function"

    def test_destructor(self, coverage):
        """Test destructor."""
        qualified, simple = coverage._extract_function_name(
            "MyClass::~MyClass()"
        )
        assert "~MyClass" in simple

    def test_no_namespace_with_params(self, coverage):
        """Test function with params but no namespace."""
        qualified, simple = coverage._extract_function_name(
            "simpleFunc(int, char*)"
        )
        assert qualified == "simpleFunc"
        assert simple == "simpleFunc"

    def test_static_method(self, coverage):
        """Test static method (looks same as regular method)."""
        qualified, simple = coverage._extract_function_name(
            "MyClass::staticMethod()"
        )
        assert qualified == "MyClass::staticMethod"
        assert simple == "staticMethod"

    def test_inline_method(self, coverage):
        """Test inline method."""
        qualified, simple = coverage._extract_function_name(
            "MyClass::inlineMethod()"
        )
        assert qualified == "MyClass::inlineMethod"
        assert simple == "inlineMethod"

    def test_virtual_method(self, coverage):
        """Test virtual method (looks same as regular method after demangling)."""
        qualified, simple = coverage._extract_function_name(
            "Base::virtualMethod()"
        )
        assert qualified == "Base::virtualMethod"
        assert simple == "virtualMethod"

    def test_deeply_nested(self, coverage):
        """Test deeply nested namespace/class."""
        qualified, simple = coverage._extract_function_name(
            "Level1::Level2::Level3::Level4::Level5::deepFunc()"
        )
        assert qualified == "Level1::Level2::Level3::Level4::Level5::deepFunc"
        assert simple == "deepFunc"

    def test_std_library_function(self, coverage):
        """Test standard library function."""
        qualified, simple = coverage._extract_function_name(
            "std::cout::operator<<(const char*)"
        )
        assert simple == "operator<<"
        assert "std::cout::operator<<" in qualified


class TestDemangleCxxNames:
    """Test the demangle_cxx_names method."""

    @pytest.fixture
    def coverage(self, tmp_path):
        """Create a LibCoverage instance for testing."""
        return LibCoverage([], str(tmp_path))

    def test_demangle_preserves_non_mangled(self, coverage):
        """Test that non-mangled text is preserved."""
        input_text = "Function 'my_c_function'"
        output = coverage.demangle_cxx_names(input_text)

        # Should preserve the format but extract simple name
        assert "Function" in output
        assert "my_c_function" in output

    def test_demangle_multiple_functions(self, coverage):
        """Test demangling multiple function entries."""
        input_text = """Function 'func1'
Some other line
Function 'func2'"""
        output = coverage.demangle_cxx_names(input_text)

        # Both functions should be present
        assert "func1" in output
        assert "func2" in output

    def test_demangle_handles_cxxfilt_unavailable(self, coverage):
        """Test graceful handling when c++filt is unavailable."""
        # Set flag to indicate c++filt is not available
        coverage._has_cxxfilt = False

        input_text = "Function '_Z10myFunctionv'"
        output = coverage.demangle_cxx_names(input_text)

        # Should return original text unchanged
        assert output == input_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
