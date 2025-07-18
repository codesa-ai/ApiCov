import os
import json
from typing import List, Dict, Optional
from pathlib import Path
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import textwrap
import logging


class DocGen:
    """
    A class to extract API documentation from Doxygen-generated HTML or XML files.
    
    This class provides functionality to parse Doxygen documentation and extract
    structured API documentation for specified functions. It can handle both
    HTML files (converting them to XML for parsing) and existing XML files.
    
    The class extracts the following information for each API and merges it into
    a single comprehensive documentation string:
    - Function prototype/signature (definition + argsstring)
    - Brief description (all paragraphs concatenated)
    - Detailed description (all paragraphs concatenated)
    - Parameter descriptions (name and description for each parameter)
    - Return value descriptions
    
    Attributes:
        doxygen_path (Path): Path to the Doxygen documentation directory
        xml_files (List[str]): List of XML file paths for parsing
        api_docs (Dict[str, str]): Dictionary storing extracted API documentation
        _xml (bool): Whether the documentation uses XML files instead of HTML
    
    Methods:
        extract_all_paras(parent): Concatenate all <para> elements under a parent element
        _extract_api_documentation_xml(apis): Extract documentation from XML files
        _extract_api_documentation_html_xml(apis): Extract documentation from HTML-converted XML
        generate_apidoc(api_list): Generate documentation for a list of APIs
        generate_json(output_file): Save documentation to JSON file
    
    Example:
        # Extract documentation from HTML files
        docgen = DocGen("/path/to/doxygen/html")
        api_list = ["function1", "function2"]
        docs = docgen.generate_apidoc(api_list)
        
        # Extract documentation from existing XML files
        docgen = DocGen("/path/to/xml/files", xml=True)
        docs = docgen.generate_apidoc(api_list)
        
        # Save to JSON file
        docgen.generate_json("output.json")
    
    Dependencies:
        - beautifulsoup4: For HTML/XML parsing
        - lxml: For XML parsing (recommended for better performance)
        - xml.etree.ElementTree: For XML parsing
    """
    def __init__(self, doxygen_path: str, xml=False):
        """
        Initialize the DocGen class.
        
        Args:
            doxygen_path (str): Path to the Doxygen-generated documentation directory
            xml (bool): Whether the documentation has XML files instead of HTML files
        """
        self.xml_files = []
        self._xml = xml
        self.doxygen_path = Path(doxygen_path)
        if not xml:
            os.makedirs(self.doxygen_path / "apicov_xml", exist_ok=True)
            self.convert_html_directory_to_xml(self.doxygen_path, self.doxygen_path / "apicov_xml")
        else:
            self.xml_files = self._find_xml_files()
        self.api_docs = {}
    
    def _find_xml_files(self):
        """
        Find all XML files in the Doxygen documentation directory.
        """
        xml_files = []

        for root, dir, files in os.walk(self.doxygen_path):
            for file in files:
                if not file.endswith(".xml"):
                    continue
                xml_file = os.path.join(root, file)
                xml_files.append(xml_file)

        return xml_files

    def _convert_html_file_to_xml(self, input_path, output_path):
        """
        Converts a single HTML file to XML using BeautifulSoup.
        """
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except UnicodeDecodeError:
            with open(input_path, "r", encoding="latin-1") as f:
                html_content = f.read()

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Write XML
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(soup.prettify(formatter="minimal"))
        self.xml_files.append(output_path)

    def convert_html_directory_to_xml(self, input_dir, output_dir):
        """
        Walks through input_dir recursively, converts all .html/.htm files to XML,
        and writes them to the same relative path in output_dir.
        """
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith((".html", ".htm")):
                    input_path = os.path.join(root, file)

                    # Build corresponding output path
                    relative_path = os.path.relpath(input_path, input_dir)
                    output_path = os.path.join(output_dir, relative_path)

                    # Change extension to .xml
                    output_path = os.path.splitext(output_path)[0] + ".xml"

                    # Ensure output folder exists
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)

                    print(f"Converting: {input_path} → {output_path}")
                    self._convert_html_file_to_xml(input_path, output_path) 

    def _read_proto(self, member):
        proto = []
        proto.append(member.find("definition").text)

        proto.append(member.find("argsstring").text)
    
        return " ".join(proto)

    def _read_details(self, member):
        details = []
        paras = member.findall("para")

        for para in paras:
            if para.text:
                details.append(para.text.strip())
        
            parameter_list = para.find("parameterlist")
            if parameter_list is not None and parameter_list.attrib.get("kind") == "param":
                for param in parameter_list.findall("parameteritem"):
                    if param.find(".//parametername") is not None:
                        param_name = param.find(".//parametername").text 
                    else:
                        param_name = "Unnamed parameter"
                    if param.find(".//parameterdescription/para") is not None:
                        param_desc = param.find(".//parameterdescription/para").text
                    else:
                        param_desc = "No description"
                    details.append(f"Param `{param_name}`: {param_desc}")
            
            for simplesect in para.findall("simplesect"):
                kind = simplesect.attrib.get("kind")
                sect_text = simplesect.find("para").text if simplesect.find("para") is not None else ""
                if kind == "return":
                    details.append(f"Returns: {sect_text}")

        return "\n".join(details)

    def _read_proto(self, member):
        proto = []
        proto.append(member.find("definition").text)

        proto.append(member.find("argsstring").text)
        
        return " ".join(proto)

    def _read_details(self, member):
        details = []
        paras = member.findall("para")

        for para in paras:
            if para.text:
                details.append(para.text.strip())
        
            parameter_list = para.find("parameterlist")
            if parameter_list is not None and parameter_list.attrib.get("kind") == "param":
                for param in parameter_list.findall("parameteritem"):
                    if param.find(".//parametername") is not None:
                        param_name = param.find(".//parametername").text 
                    else:
                        param_name = "Unnamed parameter"
                    if param.find(".//parameterdescription/para") is not None:
                        param_desc = param.find(".//parameterdescription/para").text
                    else:
                        param_desc = "No description"
                    details.append(f"Param `{param_name}`: {param_desc}")
            
            for simplesect in para.findall("simplesect"):
                kind = simplesect.attrib.get("kind")
                sect_text = simplesect.find("para").text if simplesect.find("para") is not None else ""
                if kind == "return":
                    details.append(f"Returns: {sect_text}")

        return "\n".join(details)

    def extract_all_paras(self, parent):
        """
        Concatenate all <para> elements under the given parent element.
        
        This method extracts text from all <para> elements within a parent XML element,
        concatenating them with newlines. This ensures that multi-paragraph descriptions
        are captured completely rather than just the first paragraph.
        
        Args:
            parent: XML element that may contain <para> child elements
            
        Returns:
            str: Concatenated text from all <para> elements, or empty string if no parent
        """
        if parent is None:
            return ""
        return "\n".join(
            "".join(para.itertext()).strip()
            for para in parent.findall("para")
        )

    def _extract_api_documentation_xml(self, apis):
        """
        Extract documentation for a list of APIs from XML files.
        
        This method parses Doxygen XML files to extract comprehensive documentation
        for each API function. It extracts and merges the following information:
        - Function prototype (definition + argsstring)
        - Brief description (all paragraphs)
        - Detailed description (all paragraphs) 
        - Parameter information (name and description for each parameter)
        - Return value information
        
        The documentation is merged into a single string per API with clear sections.
        
        Args:
            apis (List[str]): List of API function names to extract documentation for
            
        Returns:
            Dict[str, str]: Dictionary mapping API names to merged documentation strings
        """
        import textwrap
        api_docs = {}
        logging.info(f"DEBUG: Final result - found documentation for {len(api_docs)} APIs")
        logging.info(f"DEBUG: APIs with documentation: {list(api_docs.keys())}")
        
        for xml_file in self.xml_files:
            try:
                tree = ET.parse(xml_file)
                xmlroot = tree.getroot()
                memberdefs = xmlroot.findall(".//memberdef[@kind='function']")
                for member in memberdefs:
                    func_name = member.findtext("name")
                    if func_name not in apis:
                        continue
                    definition = member.findtext("definition")
                    argsstring = member.findtext("argsstring")
                    proto = f"{definition}{argsstring}" if definition and argsstring else definition or ''
                    brief = self.extract_all_paras(member.find("briefdescription"))
                    detailed = self.extract_all_paras(member.find("detaileddescription"))

                    # Extract parameters
                    params = []
                    for plist in member.findall("parameterlist[@kind='param']"):
                        for pitem in plist.findall("parameteritem"):
                            pname = pitem.findtext("parameternamelist/parametername") or 'unnamed'
                            pdesc = pitem.findtext("parameterdescription/para") or ''
                            params.append(f"  {pname}: {pdesc}")
                    params_str = "\n".join(params)

                    # Extract return value
                    returns = []
                    for simplesect in member.findall("detaileddescription/simplesect[@kind='return']"):
                        rtext = simplesect.findtext("para")
                        if rtext:
                            returns.append(rtext)
                    returns_str = "\n".join(returns)

                    # Merge all info into one string
                    doc_lines = []
                    if proto:
                        doc_lines.append(proto)
                    if brief:
                        doc_lines.append(f"Brief: {brief}")
                    if detailed:
                        doc_lines.append(f"Details: {detailed}")
                    if params:
                        doc_lines.append("Parameters:")
                        doc_lines.append(params_str)
                    if returns:
                        doc_lines.append(f"Returns: {returns_str}")
                    doc_string = "\n".join(doc_lines)

                    api_docs[func_name] = doc_string.strip()
            except Exception as e:
                logging.info(f"DEBUG: Error processing {xml_file}: {e}")
                continue
        logging.info(f"DEBUG: Final result - found documentation for {len(api_docs)} APIs")
        logging.info(f"DEBUG: APIs with documentation: {list(api_docs.keys())}")
        return api_docs
    def _extract_api_documentation_html_xml(self, apis):
        """
        Extract documentation for a list of APIs from HTML-like XML files (from BeautifulSoup).
        """
        from bs4 import BeautifulSoup
        api_docs = {}
        for xml_file in self.xml_files:
            with open(xml_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'xml')

            # Get function name from <h1>
            h1 = soup.find('h1')
            if not h1:
                continue
            api_name = h1.get_text(strip=True)
            if api_name not in apis:
                continue

            # Get prototype from <pre><b>...</b></pre>
            proto = ''
            pre = soup.find('pre')
            if pre and pre.b:
                proto = pre.b.get_text(strip=True)

            # Get main description from first <p> after <h1>
            desc = ''
            p_tags = h1.find_all_next('p')
            if p_tags:
                desc = p_tags[0].get_text(" ", strip=True)

            # Get parameters from <h3>Parameters</h3> and following <dl>
            params = []
            h3_params = soup.find('h3', string=lambda s: s and 'Parameter' in s)
            if h3_params:
                dl = h3_params.find_next('dl')
                if dl:
                    for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                        param_name = dt.get_text(" ", strip=True)
                        param_desc = dd.get_text(" ", strip=True)
                        params.append(f"{param_name}: {param_desc}")

            # Get return values from <h3>Return Values</h3> and following <dl>
            returns = []
            h3_ret = soup.find('h3', string=lambda s: s and 'Return Value' in s)
            if h3_ret:
                dl = h3_ret.find_next('dl')
                if dl:
                    for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                        ret_name = dt.get_text(" ", strip=True)
                        ret_desc = dd.get_text(" ", strip=True)
                        returns.append(f"{ret_name}: {ret_desc}")

            doc_string = f"{proto}\n\n{desc}"
            if params:
                doc_string += "\n\nParameters:\n" + "\n".join(params)
            if returns:
                doc_string += "\n\nReturn Values:\n" + "\n".join(returns)

            api_docs[api_name] = doc_string.strip()
        return api_docs
    
    def generate_json(self, output_file: str) -> bool:
        """
        Generate a JSON file with API documentation.
        
        Args:
            output_file (str): Path to the output JSON file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_docs, f, indent=2, ensure_ascii=False)
                print(f"Generated documentation JSON file: {output_file}")
            return True
        except Exception as e:
            print(f"Error generating JSON file: {e}")
            return False

    def generate_apidoc(self, api_list: List[str]) -> Dict[str, str]:
        """
        Generate a dictionary with API documentation.
        
        This method extracts documentation for the specified APIs and logs information
        about the extraction process, including warnings for missing APIs.
        
        Args:
            api_list (List[str]): List of API names to extract documentation for
            
        Returns:
            Dict[str, str]: Dictionary with API names as keys and documentation as values.
                           Missing APIs will not be present in the returned dictionary.
        """
        try:
            logging.debug(f"DEBUG: generate_apidoc called with {len(api_list)} APIs")
            logging.debug(f"DEBUG: API list: {api_list}")
            logging.debug(f"DEBUG: Using XML mode: {self._xml}")
            logging.debug(f"DEBUG: XML files found: {len(self.xml_files)}")
            
            if self._xml:
                self.api_docs = self._extract_api_documentation_xml(api_list)
            else:
                self.api_docs = self._extract_api_documentation_html_xml(api_list)
            
            
            # Check which APIs are missing
            missing_apis = [api for api in api_list if api not in self.api_docs]
            if missing_apis:
                logging.info(f"WARNING: Missing Documentation for APIs: {missing_apis}")
            
            logging.info(f"Extracted documentation for {len([k for k, v in self.api_docs.items() if v])} out of {len(api_list)} APIs")
            
            return self.api_docs
            
        except Exception as e:
            print(f"Error generating documentation for APIs: {e}")
            return {}


def main():
    """
    Example usage of the DocGen class.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract API documentation from Doxygen files')
    parser.add_argument('doxygen_path', help='Path to Doxygen documentation directory')
    parser.add_argument('api_list', help='JSON file containing a list of API names')
    parser.add_argument('output_file', help='Output JSON file path')
    parser.add_argument('--xml', action='store_true', help='Use XML files instead of HTML files')
    parser.add_argument('--list-apis', action='store_true', help='List available APIs instead of extracting')
    
    args = parser.parse_args()
    
    docgen = DocGen(args.doxygen_path)
    
    try:
        with open(args.api_list, 'r', encoding='utf-8') as jsonfile:
            api_data = json.load(jsonfile)
            api_list = api_data["apis"]

        if not isinstance(api_list, list):
            print("Error: JSON file must contain a list of API names.")
            return
    except FileNotFoundError:
        print(f"Error: JSON file '{args.api_list}' not found")
        return
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return
    if not api_list:
        print("Warning: No APIs found in the JSON file")
        return
    api_docs = docgen.generate_apidoc(api_list)
    if api_docs:
        success = docgen.generate_json(args.output_file)
        if success:
            print("Documentation extraction completed successfully!")
        else:
            print("Documentation extraction failed!")
    else:
        print("Documentation extraction failed!")


if __name__ == "__main__":
    main()
