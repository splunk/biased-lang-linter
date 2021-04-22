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
        with:
          token: ${{secrets.GITHUB_TOKEN}}
          path: $GITHUB_WORKSPACE
          url: $GITHUB_SERVER_URL
          repo: $GITHUB_REPOSITORY
```

3. Commit your changes

    When you merge this biased language stage into your GitHub Actions for the first time, look for a job named `Detecting Biased Language` in any pipelines triggered.

Congratulations! Pink Panther is ready to use in GitHub Actions