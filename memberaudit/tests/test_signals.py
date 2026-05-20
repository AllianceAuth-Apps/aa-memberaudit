from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories_2 import (
    ComplianceGroupDesignationFactory,
    GroupFactory,
)


class TestSignals(NoSocketsTestCase):
    def test_should_prevent_making_compliance_group_non_internal(self):
        # given
        group = GroupFactory()
        ComplianceGroupDesignationFactory(group=group)

        # when
        group.authgroup.internal = False
        group.authgroup.save()

        # then
        group.refresh_from_db()
        self.assertTrue(group.authgroup.internal)

    def test_should_allow_making_other_groups_non_internal(self):
        # given
        group = GroupFactory()

        # when
        group.authgroup.internal = False
        group.authgroup.save()

        # then
        group.refresh_from_db()
        self.assertFalse(group.authgroup.internal)

    def test_should_allow_creating_non_internal_groups(self):
        # when
        group = GroupFactory(authgroup__internal=False)

        # then
        group.refresh_from_db()
        self.assertFalse(group.authgroup.internal)
