# Contributing to Member Audit

Member Audit welcomes every contribution to Member Audit!
If you are unsure whether your idea is a good fit, please do not hesitate to open an issue or ask one of the maintainers on Discord.

To make sure your merge request can pass our CI and gets accepted we kindly ask you to follow the instructions below:

## Development environment

To develop and test your change you will need a development environment on your local machine. There are many different options to choose from. But please make sure that you can run pre-commit checks and tox tests on your local machine.

If you are on Windows or Linux you can use the [AA guide for setting up a dev environment](https://allianceauth.readthedocs.io/en/latest/development/dev_setup/aa-dev-setup-wsl-vsc-v2.html).

## Coding style

Our project follow the same coding style as the Django project: [Django Coding Style](https://docs.djangoproject.com/en/4.2/internals/contributing/writing-code/coding-style/). This includes pre-commit, black, isort & flake8.

In addition we use [pylint](https://pylint.readthedocs.io/en/latest/) to identify issues, ensure adherence to coding standards and identify code smells for refactoring.

## Branching

We strongly recommend to create a new branch for every new feature or change you plan to be submitting as merge request. Please do not create merge requests from your master branch, as that may conflict with the master branch from the main repository.

## Tests

Please update existing or provide additional unit tests for your changes. Note that your merge request might fail if it reduces the current level of test coverage.

We are using [Python unittest](https://docs.python.org/3/library/unittest.html) with the Django `TestCase` class for all tests. In addition we are using following 3rd party test tools:

- django-webtest / [WebTest](https://docs.pylonsproject.org/projects/webtest/en/latest/) - testing the web UI
- [request-mock](https://requests-mock.readthedocs.io/en/latest/) - testing requests with the requests library
- [tox](https://tox.wiki/en/latest/) - Running the test suite
- [coverage](https://coverage.readthedocs.io/en/6.4.1/) - Measuring the test coverage

## Creating the merge request

Before submitting the merge request we recommend to execute these two tox runs locally and make sure they pass.

```sh
tox -e pylint
```

```sh
tox -e py311-django40
```

Please feel free to create your merge request early and while you are still not finished developing to flag that you are working on a specific topic. Merge request that are not yet ready to review should be marked as DRAFT.

You can signal others that your merge request is ready for review by removing the DRAFT flag again.
