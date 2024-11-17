# Base Template

## Environment setup

To use this library/repo, make sure that you have Python >= `3.9.*` - we recommend using [pyenv][] for managing different
Python versions (see: [how to install pyenv on MacOS][]).

This project defines dependencies in [pyproject.toml](./pyproject.toml) according to [PEP-621](https://peps.python.org/pep-0621/)
For development create virtual env with:
```bash
python -m venv venv
source venv/bin/activate
```
Then run:
```bash
make install
```

[pyenv]: https://github.com/pyenv/pyenv#installationbrew
[how to install pyenv on MacOS]: https://jordanthomasg.medium.com/python-development-on-macos-with-pyenv-2509c694a808
