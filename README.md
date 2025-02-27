# ApiCov

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

To add this action to a workflow you need to include it towards the end of your workflow file to ensure all tests have run. An example is shown below
```
- name: 'ApiCov'
uses: pengwinsurf/ApiCov@v0.0.10-pre
with:
    install_path: ${{ steps.install.directory }} # Install path as part of your workflow.
    root_path: ${{ github.workspace }}
```

### Outputs
The action produces two files
* apis.json 
* api_coverage.json

The first file lists all the APIs identified by ApiCov and the second file lists the coverage percentage along with the size in number of lines for each API. 

Currently the action just uploads the two files as artifacts. Upload to a server for visualization is WIP. 

