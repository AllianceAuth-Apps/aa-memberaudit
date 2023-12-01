import os
import sys
from pathlib import Path
from string import Template


def main():
    myauth_dir = Path(__file__).parent.parent.parent.parent / "myauth"
    sys.path.insert(0, str(myauth_dir))

    import django

    # init and setup django project
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
    print("AA starting up...")
    django.setup()

    """MAIN"""
    from memberaudit.models import Character

    template = Template(
        """
        @shared_task(**_task_params)
        @when_esi_is_available
        def update_character_${value}(
            character_pk: int,
            force_update: bool,
            root_task_id: Optional[str] = None,
            parent_task_id: Optional[str] = None,
        ) -> None:
            \"\"\"Update ${value} for a character from ESI.\"\"\"
            _update_character_section(
                character_pk=character_pk,
                section=Character.UpdateSection.${name},
                force_update=force_update,
                root_task_id=root_task_id,
                parent_task_id=parent_task_id,
            )
    """
    )

    sections = set(Character.UpdateSection)
    excludes = {
        Character.UpdateSection.ASSETS,
        Character.UpdateSection.MAILS,
        Character.UpdateSection.CONTACTS,
        Character.UpdateSection.CONTRACTS,
    }
    for section in sorted(sections - excludes):
        print(template.substitute(name=section.name, value=section.value))


if __name__ == "__main__":
    main()
