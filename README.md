# ApiCov GitHub Action

This is Github action that is responsible for parsing all the coverage files of a software library and uploading them.
The action will identify all exports from the target library built as part of the build process in a CI/CD pipeline. 
After your tests run, ApiCov will calculate line coverage for each API your library provides to users. 


### Pre-requisites
* The library needs to be written in C/C++.
* An Api Key obtained from adding the library to Code Sa portal.
* A Github workflow that builds the target library with coverage instrumentation (eg. `--coverage -O0` or `-fprofile-arcs -ftest-coverage`) and runs your test suite. The workflow would also test installation of the library.

### Inputs

The action requires two inputs

- Required arguments
    - **root_path**: The directory where the repo is cloned, typically this is stored in the environment variable `${{ github.workspace }}`
    - **api_key**: This is the Code Sa Api key obtained after adding the library to Code Sa portal. The Api key can be referenced in the action by using the variable `${{ secrets.APICOV_KEY }}`
      
- Optional arguments
    - **install_path**: This is the directory where you install the library after building it. This can be something like `${{ github.workspace }}/install`
    - **doxygen_path**: The path to where doxygen documentation is generated. This can be in xml or html format depending on your configuration. For example `${{ github.workspace }}/docs`
    - **xml**: If you do provide a doxygen path you can also specify if this documentation is generated in html or xml format. By default this value is false indicating that documentation is in html format.
    - **compile**: Specify the type of compiler used (gcc/clang). This will allow us to understand the format of the coverage reports generated.
    - **api_source**: Source for API extraction can be "shared-libs" (default) extracts from shared library exports or "headers" parses header files directly (useful for C++ vtables)'. The default value is shared-libs.
    - **headers_dir**: Path to directory containing header files. If not provided, defaults to `install_path/include` or `install_path`

## Outputs

The action generates and uploads the following files to Code Sa:
- `apis.json`: List of all APIs found in the project
- `api_coverage.json`: Coverage data for each API (now includes documentation if doxygen_path is provided)
- `headers.json`: A list of the header files exported by the library for users to import. 

These files are uploaded as artifacts and can be downloaded in subsequent steps.

## Using this action 

To use this action in a private repository

* Reference the action in your workflow using:
   ```yaml
      - name: Run ApiCov analysis
        uses: codesa-ai/ApiCov@latest
        with:
          root_path: ${{ github.workspace }}
          install_path: ${{ github.workspace }}/install
          api_key: ${{ secrets.APICOV_KEY }}
          doxygen_path: ${{ github.workspace }}/docs/xml
          compile: gcc
          api_source: headers
          xml: true
          headers_dir: ${{ github.workspace }}/include
    ```
You should make sure this action is invoked towards the end of your CI workflow to ensure all tests have run with coverage enabled. 

## License

MIT License

Copyright (c) 2025 ApiCov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


