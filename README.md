# Description


This is a linter that checks for biased language in a code repository.

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
      - id: biased-lang
        uses: splunk/biased-lang-linter@main
        continue-on-error: true
```

3. Commit your changes

   When you merge this biased language stage into your GitHub Actions for the first time, look for a job named `Detecting Biased Language` in any pipelines triggered.

Congratulations! Pink Panther is ready to use in GitHub Actions

## Excluding directories and files

WIP
