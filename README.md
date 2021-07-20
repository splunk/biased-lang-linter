# Description

This is a code linter that checks for biased language in a code repository. Currently the words we are searching for are listed in `word_list.csv`. 

1. [Quickstart](#quickstart)
2. [Developer Instructions](#developer-instructions)
3. [Usage Example](#usage-example)
4. [Excluding directories and files](#excluding-directories-and-files)
5. [Propose new biased words](#proposing-new-biased-words)
6. [FAQ](#frequently-asked-questions)

# Quickstart

Below are the steps needed to include this GitHub Actions to your workflow.

1. If your project doesn't have a GitHub Actions workflow, follow steps [here](https://docs.github.com/en/actions/quickstart#creating-your-first-workflow) to create one.

   1. You must have at least these 3 lines for a basic workflow template.

   ```
   name: GitHub Actions
   on: [push]
   jobs:
   ```

   **Note: You may exclude directories and files from the biased language scan.** For instructions on how, see the section on [Excluding directories and files](README.md#excluding-directories-and-files). This may be useful if you have contractual dependencies on code where biased language cannot be removed yet.

2. Copy the job below into your `.github/workflows/` yml file into the `jobs` section.

```sh
biased_lang:
    runs-on: ubuntu-latest
    name: Detecting Biased Language
    steps:
      - uses: actions/checkout@v2
      - id: biased-lang-linter
        uses: splunk/biased-lang-linter@main
        continue-on-error: true
```

Here is what the final version should look like if this is your only workflow:

```sh
name: GitHub Actions
on: [push]
jobs:
  biased_lang:
    runs-on: ubuntu-latest
    name: Detecting Biased Language
    steps:
      - uses: actions/checkout@v2
      - id: biased-lang-linter
        uses: splunk/biased-lang-linter@main
        continue-on-error: true
```

3. Commit your changes

When you merge this biased language stage into your GitHub Actions for the first time, look for a job named Detecting Biased Language in any pipelines triggered.

Congratulations! Biased Lang Linter is ready to use in the CI.

Have a question? See our [FAQ](README.md#frequently-asked-questions)

# Developer Instructions

Follow these instructions to set up Biased Lang Linter locally for development.

### Required Dependencies

- python 3.7+
- ripgrep (Installation instructions [here](https://github.com/BurntSushi/ripgrep#installation).

### More on [args]

Below is a list of arguments you can pass to the CLI tool.
Note: For the additional arguments you find in `run_json.py` that aren't listed below, they are for internal use.

- **`--path=`** [_**required**_] absolute path to the directory
- **`--mode=`** [_**required**_] `check` to scan for bias language
- **`--verbose`** enables explicit logging (only applicable for check mode)
- **`--err_file=`** sends any error messages to a log file of your choice, in addition to the console
- **`--splunk`** [_**splunk_required**_] not available yet
- **`--splunk_token=`** [_**splunk_required**_] not available yet
- **`--url=`** [_**splunk_required**_] the project url. This will be the `sourcetype` in Splunk.
- **`--github_repo=`** [_**github_only**_] the repository path for repo's run in GitHub Actions. Also acts as a flag to confirm GitHub environment


### Usage Example

`biased-lang` will be run in its own dir and can target any other project through the `--path` arg.

Minimal usage for a local run:

```sh
# JSON output
python3 run_json.py --mode=check --path=/user/jdoe/git/myProject
```

## Understanding the JSON output

#### biased-language-summary.json

`biased-language-summary.json` contains a summary of which files contain which biased words.
(With `--verbose`, this output is capable of line-by-line reporting instead of a summary. The GitLab CI uses the summarized version.)

```sh
{
    "terms_found": "true" | "false",
    "mode": "check",
    "verbose": "true" | "false",
    "total_lines_matched": "295",
    "total_files_matched": "54",
    "total_words_matched": "449",
    "terms_found": "true",
    "biased_words": [list of biased words to be checked],
    "biased_word_1": { # for each biased word
        "biased_word": "biased_word_1",
        "files": [list of absolute paths to files containing biased terminology],
        "lines": [ # field included only if verbose = true. list of JSONs with details of each line found
            {
                "line": "content of line containing biased language",
                "location": {
                  "path": "dir1/dir2/file.txt",
                  "lines": {
                    "begin": "3"
                  }
                }
            },
            ...
        ],
        "num_matched_lines": "8",
        "num_matched_files": "4",
        "num_matched_words": "11"
    }
}
```

## Formatting of word_list.csv

The biased words are listed on a new line in the `word_list.csv` file.

## Proposing new biased words

TBD

## Excluding directories and files

The tool automatically excludes a few common directories you would already want to exclude such as `node_modules`, `__pycache__`, and `.git`.

To exclude additional directories or files in your repo from the scan, create a `.biased_lang_exclude` file at the project root. Add each directory or file you'd like to exclude on a new line. This will respect .gitignore glob patterns (i.e dir1/**/dir4)
**Caution:\*\* Please do not include any empty lines in this file. Each line of the file represents something to ignore in the search.

## Splunk Results

TBD

## Frequently Asked Questions

**Q: My `Biased Language Detection` job passed with warnings, but I didn't add any new instances of biased language. What does this mean?**

**A:** Every time a pipeline runs with the `biased_lang` stage, it scans the entire repository.
If the pipeline detects biased language anywhere in the repository, the `biased_lang` stage will pass with warnings and show an orange exclamation point instead of a green check.

**Q: I'm including git submodules in my repo and seems to be breaking the workflow, what can I do?**

**A:** You'll need to add your submodule paths in the `.biased_lang_exclude` file. You can find info on how to (exclude files and directories here)[#excluding-directories-and-files]

## Learn More

- Bias Free Communication: [Splunk Style Guide](https://docs.splunk.com/Documentation/StyleGuide/current/StyleGuide/Inclusivity)