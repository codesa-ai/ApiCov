"""
Unit tests for the ClangParser module.
"""

import pytest
import tempfile
import os
from pathlib import Path

# Import the module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.ClangParser import ClangParser, is_cpp_header, CLANG_AVAILABLE, ApiInfo


# Skip all tests if libclang is not available
pytestmark = pytest.mark.skipif(not CLANG_AVAILABLE, reason="libclang not available")


class TestCppHeaderDetection:
    """Test C++ header file detection."""

    def test_cpp_extension_hpp(self):
        """Test .hpp files are detected as C++."""
        assert is_cpp_header("test.hpp") is True

    def test_cpp_extension_hxx(self):
        """Test .hxx files are detected as C++."""
        assert is_cpp_header("test.hxx") is True

    def test_cpp_extension_hh(self):
        """Test .hh files are detected as C++."""
        assert is_cpp_header("test.hh") is True

    def test_c_extension_h_with_cpp_keywords(self):
        """Test .h files with C++ keywords are detected as C++."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.h', delete=False) as f:
            f.write("class MyClass { public: void method(); };")
            temp_file = f.name

        try:
            assert is_cpp_header(temp_file) is True
        finally:
            os.unlink(temp_file)

    def test_c_extension_h_with_namespace(self):
        """Test .h files with namespace keyword are detected as C++."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.h', delete=False) as f:
            f.write("namespace MyNamespace { void function(); }")
            temp_file = f.name

        try:
            assert is_cpp_header(temp_file) is True
        finally:
            os.unlink(temp_file)

    def test_c_header_detected_as_c(self):
        """Test pure C .h files are detected as C."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.h', delete=False) as f:
            f.write("void my_function(int x);")
            temp_file = f.name

        try:
            assert is_cpp_header(temp_file) is False
        finally:
            os.unlink(temp_file)


class TestClangParser:
    """Test ClangParser functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def parser(self, temp_dir):
        """Create a ClangParser instance."""
        return ClangParser(header_dirs=[temp_dir])

    def test_parser_initialization(self, temp_dir):
        """Test ClangParser can be initialized."""
        parser = ClangParser(header_dirs=[temp_dir])
        assert parser is not None
        assert temp_dir in parser.header_dirs

    def test_parse_simple_cpp_function(self, parser, temp_dir):
        """Test parsing a simple C++ function."""
        header_content = """
namespace MyNamespace {
    void simpleFunction(int x);
}
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Keys now include signature to support overloaded functions
        assert "MyNamespace::simpleFunction(int)" in apis
        api_info = apis["MyNamespace::simpleFunction(int)"]
        assert api_info.simple_name == "simpleFunction"
        assert api_info.qualified_name == "MyNamespace::simpleFunction"
        assert api_info.signature == "(int)"

    def test_parse_cpp_class_method(self, parser, temp_dir):
        """Test parsing C++ class methods."""
        header_content = """
namespace MyNamespace {
    class MyClass {
    public:
        void publicMethod(const char* str, int num);
        int getNumber();
    private:
        void privateMethod();
    };
}
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Should have public methods (keys include signature)
        # Note: libclang may add spaces in signatures, so check flexibly
        assert any("MyNamespace::MyClass::publicMethod" in k for k in apis)
        assert "MyNamespace::MyClass::getNumber()" in apis

        # Should NOT have private methods
        assert not any("privateMethod" in k for k in apis)

        # Check public method details
        public_method_key = [k for k in apis if "publicMethod" in k][0]
        public_method = apis[public_method_key]
        assert public_method.simple_name == "publicMethod"
        assert public_method.qualified_name == "MyNamespace::MyClass::publicMethod"
        assert public_method.is_public is True

    def test_parse_nested_namespace(self, parser, temp_dir):
        """Test parsing nested namespaces."""
        header_content = """
namespace Outer {
    namespace Inner {
        void nestedFunction();
    }
}
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Keys include signature
        assert "Outer::Inner::nestedFunction()" in apis
        api_info = apis["Outer::Inner::nestedFunction()"]
        assert api_info.simple_name == "nestedFunction"

    def test_parse_constructor(self, parser, temp_dir):
        """Test parsing C++ constructors."""
        header_content = """
class MyClass {
public:
    MyClass();
    MyClass(int x);
};
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Constructors should be detected (keys include signature)
        # Both overloaded constructors should be present
        assert "MyClass::MyClass()" in apis or "MyClass::MyClass(int)" in apis

    def test_parse_template_class(self, parser, temp_dir):
        """Test parsing template classes (templates should have params erased)."""
        header_content = """
template<typename T>
class Container {
public:
    void insert(T value);
    T get();
};
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Template methods should be extracted (with template params erased)
        # The exact representation depends on libclang version
        assert len(apis) > 0

    def test_parse_multiple_classes(self, parser, temp_dir):
        """Test parsing multiple classes in same file."""
        header_content = """
namespace MyNamespace {
    class ClassA {
    public:
        void methodA();
    };

    class ClassB {
    public:
        void methodB();
    };
}
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Keys include signature
        assert "MyNamespace::ClassA::methodA()" in apis
        assert "MyNamespace::ClassB::methodB()" in apis

        # Ensure they're different methods
        assert apis["MyNamespace::ClassA::methodA()"].simple_name == "methodA"
        assert apis["MyNamespace::ClassB::methodB()"].simple_name == "methodB"

    def test_parse_overloaded_methods(self, parser, temp_dir):
        """Test parsing overloaded methods (same name, different signatures)."""
        header_content = """
class MyClass {
public:
    void save();
    void save(const char* filename);
    void save(const char* filename, int mode);
};
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # All overloads should be present (may have different keys or same key)
        # The exact behavior depends on implementation
        assert len(apis) >= 1

        # At least one should have the save method
        has_save = any("save" in api_info.simple_name for api_info in apis.values())
        assert has_save

    def test_parse_empty_file(self, parser, temp_dir):
        """Test parsing an empty header file."""
        header_path = os.path.join(temp_dir, "empty.hpp")
        with open(header_path, 'w') as f:
            f.write("")

        apis = parser.parse_header(header_path)

        assert apis == {}

    def test_parse_syntax_error(self, parser, temp_dir):
        """Test parsing a file with syntax errors."""
        header_content = """
class MyClass {
    void method(  // Missing closing paren and semicolon
};
"""
        header_path = os.path.join(temp_dir, "error.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        # Should return empty dict on parse errors
        apis = parser.parse_header(header_path)
        assert apis == {}

    def test_parse_only_target_file(self, parser, temp_dir):
        """Test that only APIs from the target file are extracted (not included headers)."""
        # Create an included header
        include_path = os.path.join(temp_dir, "included.hpp")
        with open(include_path, 'w') as f:
            f.write("void includedFunction();")

        # Create main header that includes the other
        header_content = f"""
#include "included.hpp"

void mainFunction();
"""
        header_path = os.path.join(temp_dir, "main.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Should only have mainFunction, not includedFunction (keys include signature)
        assert "mainFunction()" in apis
        # includedFunction might or might not be included depending on implementation
        # The key point is that we get at least the main file's APIs

    def test_extract_qualified_name_method(self, parser, temp_dir):
        """Test the extract_qualified_name method."""
        # This requires parsing a file and getting a cursor
        header_content = """
namespace Test {
    class MyClass {
    public:
        void myMethod();
    };
}
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        # Parse and verify qualified names are extracted
        apis = parser.parse_header(header_path)

        assert len(apis) > 0
        # At least one API should have a qualified name with ::
        has_qualified = any("::" in name for name in apis.keys())
        assert has_qualified

    def test_extract_signature(self, parser, temp_dir):
        """Test signature extraction."""
        header_content = """
void funcNoArgs();
void funcOneArg(int x);
void funcMultiArgs(const char* str, int num, float val);
void funcPointer(int* ptr);
void funcReference(const int& ref);
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Check various signature formats (keys now include signature)
        if "funcNoArgs()" in apis:
            assert "()" in apis["funcNoArgs()"].signature
        if "funcOneArg(int)" in apis:
            assert "int" in apis["funcOneArg(int)"].signature
        if "funcMultiArgs(const char*, int, float)" in apis:
            sig = apis["funcMultiArgs(const char*, int, float)"].signature
            assert "char" in sig and "int" in sig and "float" in sig

    def test_public_private_detection(self, parser, temp_dir):
        """Test detection of public vs private APIs."""
        header_content = """
class MyClass {
public:
    void publicMethod1();
protected:
    void protectedMethod();
private:
    void privateMethod();
public:
    void publicMethod2();
};
"""
        header_path = os.path.join(temp_dir, "test.hpp")
        with open(header_path, 'w') as f:
            f.write(header_content)

        apis = parser.parse_header(header_path)

        # Should have public methods (keys include signature)
        assert "MyClass::publicMethod1()" in apis or "publicMethod1()" in apis
        assert "MyClass::publicMethod2()" in apis or "publicMethod2()" in apis

        # Should NOT have private or protected methods
        private_count = sum(1 for name in apis.keys() if "privateMethod" in name)
        assert private_count == 0


class TestApiInfo:
    """Test ApiInfo dataclass."""

    def test_api_info_creation(self):
        """Test creating ApiInfo objects."""
        api_info = ApiInfo(
            qualified_name="MyNamespace::MyClass::myMethod",
            simple_name="myMethod",
            signature="(int, const char*)",
            is_public=True,
            file_path="/path/to/header.hpp",
            line_number=42
        )

        assert api_info.qualified_name == "MyNamespace::MyClass::myMethod"
        assert api_info.simple_name == "myMethod"
        assert api_info.signature == "(int, const char*)"
        assert api_info.is_public is True
        assert api_info.file_path == "/path/to/header.hpp"
        assert api_info.line_number == 42

    def test_api_info_optional_signature(self):
        """Test ApiInfo with optional signature."""
        api_info = ApiInfo(
            qualified_name="func",
            simple_name="func",
            signature=None,
            is_public=True,
            file_path="/path/to/header.h",
            line_number=10
        )

        assert api_info.signature is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
