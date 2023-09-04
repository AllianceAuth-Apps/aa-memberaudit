# flake8: noqa
"""
This is a standalone scripts for profiling code sections of Member Audit.
"""

import inspect
import os
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
myauth_dir = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(currentdir))))
    + "/myauth"
)
sys.path.insert(0, myauth_dir)


import django

# init and setup django project
print("Initializing Django...")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

import cProfile

from memberaudit.core.fittings import Fitting

from .factories import create_fitting_text


def main():
    fitting.required_skills()


fitting_text = create_fitting_text("fitting_tristan.txt")
fitting = create_fitting_from_eft(fitting_text)

cProfile.run("main()", sort="cumtime")
