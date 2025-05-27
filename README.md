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
* The directory where you install the library on the runner during your workflow. 

## Inputs

| Input | Description | Required |
|-------|-------------|----------|
| `install_path` | The directory where the build is installed | Yes |
| `root_path` | The directory where the repo is cloned | Yes |

## Outputs

The action generates two JSON files:
- `apis.json`: List of all APIs found in the project
- `api_coverage.json`: Coverage data for each API

These files are uploaded as artifacts and can be downloaded in subsequent steps.

## Private Repository Setup

To use this action in a private repository:

1. Create a new repository for the action
2. Push this code to that repository
3. Create a release with a tag (e.g., v1.0.0)
4. Reference the action in your workflow using:
   ```yaml
    - name: 'ApiCov'
    uses: your-username/apicov@v0.0.1
    with:
        install_path: ${{ steps.install.directory }} # Install path as part of your workflow.
        root_path: ${{ github.workspace }}
    ```

## License
MIT

Currently the action just uploads the two files as artifacts. Upload to a server for visualization is WIP. 

