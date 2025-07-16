# ApiCov GitHub Action

This is Github action that is responsible for parsing all the coverage files of a software library and uploading them.
The action will identify all exports from shared libraries built as part of the build process in a CI/CD pipeline. 
After your tests run, ApiCov will calculate line coverage for each API your library provides to users. 
ApiCov uses `gcov` to calculate coverage. 


### Pre-requisites
* Users of the action need to build their targets with coverage eg. `--coverage -O0` or `-fprofile-arcs -ftest-coverage -O0`.
* The library needs to be built into shared library file(s). This is to be able to identify all APIs your library provides for clients. If your library is a header only library then you need to provide the list of APIs. 
* As part of the CI/CD pipeline you need to install and run the tests on your library before running this action. So it would come towards the end of your CI/CD workflow. This would ensure that all your CI/CD tests have run successfully to ensure accurate reporting of your API coverage.

### Inputs
The action requires two inputs
* The directory where the repository is cloned on the runner. 
* The api key associated with the library. 
* (optional) The directory where you install the library on the runner during your workflow. 

## Inputs

| Input | Description | Required |
|-------|-------------|----------|
| `root_path` | The directory where the repo is cloned | Yes |
| `api_key` | The API key associated with the library | Yes |
| `install_path` | The directory where the build is installed | No |
| `doxygen_path` | Path to the Doxygen HTML files (optional, for API documentation extraction) | No |

## Outputs

The action generates two JSON files:
- `apis.json`: List of all APIs found in the project
- `api_coverage.json`: Coverage data for each API (now includes documentation if doxygen_path is provided)

These files are uploaded as artifacts and can be downloaded in subsequent steps.

## Using this action 

To use this action in a private repository

* Reference the action in your workflow using:
   ```yaml
      - name: 'ApiCov'
        uses: codesa-ai/ApiCov@v0.1.0
        with:
          root_path: ${{ github.workspace }}
          api_key: ${{ secrets.APICOV_KEY }}
          install_path: ${{ steps.install.outputs.prefix }}
          doxygen_path: ${{ steps.doxygen.outputs.html_dir }} # Optional: for API documentation extraction
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


