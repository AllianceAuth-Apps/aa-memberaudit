"""Define hooks for Alliance Auth like the sidebar menu entry."""

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from memberaudit.utils import get_unidecoded_slug

from . import urls
from .app_settings import MEMBERAUDIT_APP_NAME
from .models import Character


class MemberauditMenuItem(MenuItemHook):
    """A class to ensure only authorized users will see the menu entry."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            MEMBERAUDIT_APP_NAME,
            "far fa-address-card fa-fw fa-fw",
            "memberaudit:index",
            navactive=["memberaudit:"],
        )

    def render(self, request):
        if request.user.has_perm("memberaudit.basic_access"):
            app_count = Character.objects.characters_of_user_to_register_count(
                request.user
            )
            self.count = app_count if app_count and app_count > 0 else None
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return MemberauditMenuItem()


@hooks.register("url_hook")
def register_urls():
    base_url = get_unidecoded_slug(MEMBERAUDIT_APP_NAME)
    return UrlHook(urls, "memberaudit", r"^{base_url}/".format(base_url=base_url))
