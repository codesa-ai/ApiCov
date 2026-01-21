"""
ClangParser module for extracting C++ API information using libclang.

This module uses LLVM's libclang Python bindings to parse C++ header files
and extract qualified method names, signatures, and other API information.
"""

from dataclasses import dataclass
from typing import Optional
import logging

try:
    import clang.cindex
    from clang.cindex import Index, CursorKind, AccessSpecifier, TypeKind
    CLANG_AVAILABLE = True
except ImportError:
    CLANG_AVAILABLE = False
    logging.warning("libclang not available - falling back to regex-based parsing")


@dataclass
class ApiInfo:
    """Information about a C++ API extracted from headers."""
    qualified_name: str
    simple_name: str
    signature: Optional[str]
    is_public: bool
    file_path: str
    line_number: int


class ClangParser:
    """Parser for C++ headers using libclang."""

    def __init__(self, header_dirs: list[str] = None, compile_flags: list[str] = None):
        """
        Initialize the Clang parser.

        Args:
            header_dirs: List of directories to search for header files
            compile_flags: Additional compile flags for parsing (e.g., -std=c++17)
        """
        if not CLANG_AVAILABLE:
            raise ImportError("libclang is not available. Install with: pip install libclang")

        self.header_dirs = header_dirs or []
        self.compile_flags = compile_flags or []
        self.index = Index.create()

        # Build default compile arguments
        self.default_args = [
            '-x', 'c++',
            '-std=c++17',
        ]

        # Add include directories
        for header_dir in self.header_dirs:
            self.default_args.append(f'-I{header_dir}')

        # Add user-specified flags
        self.default_args.extend(self.compile_flags)

    def parse_header(self, header_path: str) -> dict[str, ApiInfo]:
        """
        Parse a C++ header file and extract API information.

        Args:
            header_path: Path to the header file

        Returns:
            Dictionary mapping qualified API names to ApiInfo objects
        """
        try:
            translation_unit = self.index.parse(
                header_path,
                args=self.default_args,
                options=clang.cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
            )

            if not translation_unit:
                logging.error(f"Failed to parse {header_path}")
                return {}

            # Check for fatal errors
            has_fatal_errors = any(
                diag.severity >= clang.cindex.Diagnostic.Error
                for diag in translation_unit.diagnostics
            )

            if has_fatal_errors:
                logging.warning(f"Parse errors in {header_path}:")
                for diag in translation_unit.diagnostics:
                    if diag.severity >= clang.cindex.Diagnostic.Error:
                        logging.warning(f"  {diag}")
                return {}

            # Extract APIs from the translation unit
            apis = {}
            self._walk_cursor(translation_unit.cursor, apis, header_path)

            return apis

        except Exception as e:
            logging.error(f"Error parsing {header_path}: {e}")
            return {}

    def _walk_cursor(self, cursor, apis: dict, target_file: str, namespace_stack: list[str] = None):
        """
        Recursively walk the AST and extract API information.

        Args:
            cursor: Current cursor in the AST
            apis: Dictionary to populate with API info
            target_file: Only extract APIs from this file (not included headers)
            namespace_stack: Current namespace context
        """
        if namespace_stack is None:
            namespace_stack = []

        # Only process declarations in the target file (not included headers)
        if cursor.location.file and cursor.location.file.name != target_file:
            return

        # Track namespace context
        if cursor.kind == CursorKind.NAMESPACE:
            namespace_stack.append(cursor.spelling)
            for child in cursor.get_children():
                self._walk_cursor(child, apis, target_file, namespace_stack)
            namespace_stack.pop()
            return

        # Process class/struct declarations
        if cursor.kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE):
            class_name = cursor.spelling
            if class_name:  # Skip anonymous classes
                namespace_stack.append(class_name)
                for child in cursor.get_children():
                    self._walk_cursor(child, apis, target_file, namespace_stack)
                namespace_stack.pop()
            return

        # Extract function declarations
        if cursor.kind == CursorKind.FUNCTION_DECL:
            api_info = self._extract_function_info(cursor, namespace_stack, target_file)
            if api_info and api_info.is_public:
                apis[api_info.qualified_name] = api_info

        # Extract method declarations
        elif cursor.kind == CursorKind.CXX_METHOD:
            api_info = self._extract_method_info(cursor, namespace_stack, target_file)
            if api_info and api_info.is_public:
                apis[api_info.qualified_name] = api_info

        # Extract constructors
        elif cursor.kind == CursorKind.CONSTRUCTOR:
            api_info = self._extract_constructor_info(cursor, namespace_stack, target_file)
            if api_info and api_info.is_public:
                apis[api_info.qualified_name] = api_info

        # Recurse into other children
        for child in cursor.get_children():
            self._walk_cursor(child, apis, target_file, namespace_stack)

    def _extract_function_info(self, cursor, namespace_stack: list[str], file_path: str) -> Optional[ApiInfo]:
        """Extract information about a free function."""
        function_name = cursor.spelling
        if not function_name:
            return None

        # Build qualified name
        qualified_name = self._build_qualified_name(namespace_stack, function_name)

        # Extract signature
        signature = self.extract_signature(cursor)

        return ApiInfo(
            qualified_name=qualified_name,
            simple_name=function_name,
            signature=signature,
            is_public=True,  # Free functions are always "public"
            file_path=file_path,
            line_number=cursor.location.line
        )

    def _extract_method_info(self, cursor, namespace_stack: list[str], file_path: str) -> Optional[ApiInfo]:
        """Extract information about a class method."""
        method_name = cursor.spelling
        if not method_name:
            return None

        # Check if the method is public
        if not self.is_public_api(cursor):
            return None

        # Build qualified name
        qualified_name = self._build_qualified_name(namespace_stack, method_name)

        # Extract signature
        signature = self.extract_signature(cursor)

        return ApiInfo(
            qualified_name=qualified_name,
            simple_name=method_name,
            signature=signature,
            is_public=True,
            file_path=file_path,
            line_number=cursor.location.line
        )

    def _extract_constructor_info(self, cursor, namespace_stack: list[str], file_path: str) -> Optional[ApiInfo]:
        """Extract information about a constructor."""
        # Constructor name is the class name
        if not namespace_stack:
            return None

        class_name = namespace_stack[-1]

        # Check if the constructor is public
        if not self.is_public_api(cursor):
            return None

        # Build qualified name
        qualified_name = self._build_qualified_name(namespace_stack, class_name)

        # Extract signature
        signature = self.extract_signature(cursor)

        return ApiInfo(
            qualified_name=qualified_name,
            simple_name=class_name,
            signature=signature,
            is_public=True,
            file_path=file_path,
            line_number=cursor.location.line
        )

    def _build_qualified_name(self, namespace_stack: list[str], name: str) -> str:
        """
        Build a fully qualified name from namespace/class stack and name.

        Args:
            namespace_stack: List of namespaces and classes
            name: Function/method name

        Returns:
            Qualified name like "namespace::Class::method"
        """
        if namespace_stack:
            return "::".join(namespace_stack) + "::" + name
        return name

    def extract_qualified_name(self, cursor) -> str:
        """
        Extract the fully qualified name from a cursor.

        Args:
            cursor: Clang cursor

        Returns:
            Qualified name like "namespace::Class::method"
        """
        parts = []
        current = cursor

        # Walk up the semantic parent chain
        while current:
            if current.kind in (CursorKind.NAMESPACE, CursorKind.CLASS_DECL,
                              CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE):
                if current.spelling:
                    parts.append(current.spelling)
            elif current.kind in (CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD,
                                CursorKind.CONSTRUCTOR):
                if current.spelling:
                    parts.append(current.spelling)

            current = current.semantic_parent

        # Reverse to get correct order (namespace::Class::method)
        parts.reverse()
        return "::".join(parts) if parts else ""

    def extract_simple_name(self, cursor) -> str:
        """
        Extract just the function/method name from a cursor.

        Args:
            cursor: Clang cursor

        Returns:
            Simple name like "method"
        """
        return cursor.spelling

    def extract_signature(self, cursor) -> str:
        """
        Extract the function signature (parameter types).

        Args:
            cursor: Clang cursor

        Returns:
            Signature like "(const char*, int)" or empty string if unable to extract
        """
        try:
            # Get parameter types
            params = []
            for arg in cursor.get_arguments():
                param_type = arg.type.spelling
                # Simplify template parameters (optional, can be removed if full types needed)
                # Example: std::vector<int> -> std::vector
                params.append(param_type)

            if params:
                return f"({', '.join(params)})"
            else:
                return "()"

        except Exception as e:
            logging.debug(f"Could not extract signature for {cursor.spelling}: {e}")
            return ""

    def is_public_api(self, cursor) -> bool:
        """
        Check if a cursor represents a public API.

        Args:
            cursor: Clang cursor

        Returns:
            True if the API is public, False otherwise
        """
        # For C functions, always return True
        if cursor.kind == CursorKind.FUNCTION_DECL:
            return True

        # For C++ methods, check access specifier
        if cursor.kind in (CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR):
            access = cursor.access_specifier
            return access == AccessSpecifier.PUBLIC

        return True


def is_cpp_header(file_path: str) -> bool:
    """
    Detect if a header file is C++ (vs C).

    Args:
        file_path: Path to header file

    Returns:
        True if likely a C++ header, False otherwise
    """
    # Check file extension
    cpp_extensions = ['.hpp', '.hxx', '.h++', '.hh']
    if any(file_path.endswith(ext) for ext in cpp_extensions):
        return True

    # For .h files, check content for C++ keywords
    if file_path.endswith('.h'):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(4096)  # Read first 4KB
                cpp_keywords = ['class ', 'namespace ', 'template<', 'public:', 'private:', 'protected:']
                return any(keyword in content for keyword in cpp_keywords)
        except Exception:
            pass

    return False
