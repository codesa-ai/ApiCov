from tree_sitter import Parser, Language
import tree_sitter_cpp as tscpp

parser = Parser(Language(tscpp.language()))

with open("/home/ahmedzaki/core/include/LibreOfficeKit/LibreOfficeKit.hxx", "rb") as f:
    source = f.read()

tree = parser.parse(source)
root = tree.root_node


def node_text(node):
    return source[node.start_byte:node.end_byte].decode()


public_functions = []


def walk(node, namespaces, classes, access):
    # Enter namespace
    if node.type == "namespace_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            namespaces = namespaces + [node_text(name_node)]

    # Enter class / struct
    if node.type in ("class_specifier", "struct_specifier"):
        name_node = node.child_by_field_name("name")
        if name_node:
            classes = classes + [node_text(name_node)]
            # Default access
            access = "private" if node.type == "class_specifier" else "public"

    # Handle field_declaration_list (class body) - access specifiers are siblings here
    if node.type == "field_declaration_list":
        current_access = access
        for child in node.children:
            if child.type == "access_specifier":
                current_access = node_text(child).rstrip(":").strip()
            else:
                walk(child, namespaces, classes, current_access)
        return  # Don't recurse again below

    # Function declaration or inline definition
    # Capture if: (1) public class member, or (2) standalone function in namespace (not in a class)
    is_class_member = len(classes) > 0
    is_namespace_function = len(namespaces) > 0 and not is_class_member
    should_capture = (access == "public" and is_class_member) or is_namespace_function
    
    if should_capture and node.type in ("field_declaration", "function_definition", "declaration"):
        decl = node.child_by_field_name("declarator")
        
        # Handle pointer return types: char* foo() -> pointer_declarator -> function_declarator
        if decl and decl.type == "pointer_declarator":
            decl = decl.child_by_field_name("declarator")
        
        if decl and decl.type == "function_declarator":
            name = decl.child_by_field_name("declarator")
            # Inside a class, names are field_identifier; at file scope, they're identifier
            if name and name.type in ("identifier", "field_identifier"):
                func_name = node_text(name)
                # Skip constructors (name matches class name) and destructors
                if classes and func_name == classes[-1]:
                    pass  # Constructor - skip
                else:
                    fq_name = "::".join(namespaces + classes + [func_name])
                    public_functions.append(fq_name)

    for child in node.children:
        walk(child, namespaces, classes, access)


walk(root, [], [], None)

print(public_functions)
print(len(public_functions))
