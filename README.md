# Qtsdk

## Overview

The qtsdk repository provides tools used in packaging.

## Requirements

- [Python](https://www.python.org/) 3.6 or higher
- [Pip](https://pip.pypa.io/en/stable/) version 18.0 or higher
- 7z command line utility added to PATH
- Relevant toolchains for building e.g. GCC, MinGW, MSVC

## Running the packaging scripts

Scripts in this repository are intended to be run inside a virtual environment.

The [officially recommended](https://packaging.python.org/en/latest/tutorials/managing-dependencies/#managing-dependencies) tool [Pipenv](https://pipenv.pypa.io/en/latest/) is used to manage Python dependencies and create virtualenv.

For more information see [Pipenv documentation](https://pipenv.pypa.io/en/latest/) and the following subsections.

### Setting up Python virtual environment

Use the package manager pip to install Pipenv.

Note: It is recommended to do user installation with ```--user``` to avoid breaking any system-wide packages.
```
pip install pipenv --user
```

Inside the repository, install the virtual environment from Pipfile, which contains the required Python dependencies.

This will create a virtualenv environment with the dependencies installed.

Note: It is recommended to skip Pipfile.lock generation with ```--skip-lock``` as this file is not committed to the repository.
```
pipenv install --skip-lock
```

### Using the virtual environment

Activate Pipenv shell to run commands inside the newly created virtual environment:
```
pipenv shell
```

Alternatively, to run a single command you can use```pipenv run```.
For example, the following will execute ```python --version``` printing out the Python version in the virtualenv:
```
pipenv run python --version
```

## Contributing

Instructions for Gerrit can be found in Qt Wiki: [Setting up Gerrit](https://wiki.qt.io/Setting_up_Gerrit)

### Installing the development packages

Install the development packages to your virtual environment with the ```--dev``` option:
```
pipenv install --dev --skip-lock
```

### Setting up Git hooks

Follow the instructions on [Setting up git hooks](https://wiki.qt.io/Setting_up_Gerrit#Setting_up_git_hooks) and install the following hooks:
- [commit-msg](http://codereview.qt-project.org/tools/hooks/commit-msg) hook if not already installed. (Gerrit Commit-Ids)
- (Optional) [post-commit](https://code.qt.io/cgit/qt/qtrepotools.git/plain/git-hooks/git_post_commit_hook) hook. (Sanity Bot)

#### Hooks for unit tests and quality assurance

In addition, this repository uses hooks from [pre-commit](https://pre-commit.com/) framework to run unit tests and perform several code quality checks on changed files.

The configuration file for pre-commit hooks is ```.pre-commit-config.yaml``` located at the root of the repository.

It is recommended to enable these additional hooks to spot new regressions early and ensure compliance with the code style.

The following command available in the virtual environment will enable the pre-commit hooks in the repository:
```
pre-commit install
```

If you would like to for whatever reason skip the pre-commit validations when for example working on a WIP commit, you can use ```--no-verify``` to temporarily disable hooks:
```
git commit --no-verify
```

To manually run hooks, you may use the following:

```
pre-commit run  # All hooks
pre-commit run unittest  # Only run the specified hook, 'unittest'. See the configuration file for list of hooks
```

Hint: to specify custom files to pass to the hooks, add filters ```--all-files```, ```--files <pattern>``` or ```--exclude <pattern>```

For more pre-commit usage examples and details, see the [documentation](https://pre-commit.com/)
