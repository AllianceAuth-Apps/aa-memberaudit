from app_utils.testing import NoSocketsTestCase, create_authgroup

from .testdata.factories import create_compliance_group_designation
from .testdata.load_entities import load_entities


class TestSignals(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_should_prevent_making_compliance_group_non_internal(self):
        # given
        group = create_authgroup()
        create_compliance_group_designation(group)
        # when
        group.authgroup.internal = False
        group.authgroup.save()
        # then
        group.refresh_from_db()
        self.assertTrue(group.authgroup.internal)

    def test_should_allow_making_other_groups_non_internal(self):
        # given
        group = create_authgroup()
        # when
        group.authgroup.internal = False
        group.authgroup.save()
        # then
        group.refresh_from_db()
        self.assertFalse(group.authgroup.internal)

    def test_should_allow_creating_non_internal_groups(self):
        # when
        group = create_authgroup(internal=False)
        # then
        group.refresh_from_db()
        self.assertFalse(group.authgroup.internal)
