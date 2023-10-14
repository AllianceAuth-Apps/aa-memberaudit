# flake8: noqa
"""This is a standalone scripts shows which models have permissions."""

import inspect
import os
import sys

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
myauth_dir = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    + "/myauth"
)
sys.path.insert(0, myauth_dir)
import django

# init and setup django project
print("Initializing Django...")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

from rich.pretty import pprint

from django.apps import apps

from memberaudit.models import General
from memberaudit.tests.utils import permissions_for_model


def main():
    my_app_label = General._meta.app_label
    my_models = [o for o in apps.get_models() if o._meta.app_label == my_app_label]
    my_models.sort(key=lambda o: o._meta.model_name)
    results = {}
    for model_class in my_models:
        has_permissions = permissions_for_model(model_class).exists()
        results[model_class.__name__] = has_permissions

    pprint(results)


if __name__ == "__main__":
    main()
