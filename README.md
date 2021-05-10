# pink-panther

![Banner](static/banner.jpg)

Pink Panther is a light framework that programatically checks for biased language in a code repository.

This repo includes the GitHub Action that other GitHub projects will call on.

# Quickstart

1. If your project doesn't have a GitHub Actions workflow, follow steps [here](https://docs.github.com/en/actions/quickstart#creating-your-first-workflow) to create one.
   1. You must have at least these 3 lines

```
name: Github Actions
on: [push]
jobs:
```

2. Copy the job below into your `.github/workflows/` yml file into the `jobs` section.

```sh
biased_lang:
    runs-on: ubuntu-latest
    name: Detecting Biased Language
    steps:
      - uses: actions/checkout@v2
      - id: pink-panther
        uses: splunk/pink-panther@main
```

3. Commit your changes

   When you merge this biased language stage into your GitHub Actions for the first time, look for a job named `Detecting Biased Language` in any pipelines triggered.

Congratulations! Pink Panther is ready to use in GitHub Actions

## Excluding directories and files

To exclude certain directories and files in your repo from the scan, add these custom files to specify which directories and/or files you wish to exclude:

- Any directories in an `.excluded_dirs` file will contain the names of directories that will be recursively excluded.
- Likewise, the `.excluded_files` file will contain the names of files that will be excluded.

Include the path to these files in the and `--excluded_dirs_path` and `--excluded_files_path` arguments, respectively.
Note that these paths are relative to the main path provided to `--path`.
Filetypes to ignore can be added as `*.extension`.
**Caution:** Please do not include any empty lines in these files. Each line of the file represents something to ignore in the search.

Examples:

```sh
# .excluded_dirs
node_modules
build
env
.git
```

```sh
# .excluded_files
README.md
*.test.js
build/index.js
```
