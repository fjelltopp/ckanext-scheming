import pytest
from ckanapi import LocalCKAN


@pytest.mark.usefixtures(u'clean_db')
@pytest.mark.usefixtures(u'clean_index')
class TestAutoCreateValidName(object):
    def test_prevents_duplicates(self):
        lc = LocalCKAN()
        dataset1, dataset2 = [lc.action.package_create(
            type="auto-create-valid-name", year="2020", location="north-pole"
        ) for i in range(2)]

        assert dataset1['name'] == u'north-pole-autogenerate-2020'
        assert dataset2['name'] == u'north-pole-autogenerate-2020-1'

    def test_preserves_existing_dataset_name(self):
        lc = LocalCKAN()
        dataset1 = lc.action.package_create(
            type="auto-create-valid-name", year="2020", location="north-pole"
        )
        dataset2 = lc.action.package_create(
            type="auto-create-valid-name", year="2020", location="north-pole"
        )
        lc.action.package_delete(id=dataset1['id'])

        updated_dataset2 = lc.action.package_update(**dataset2)
        assert updated_dataset2['name'] == updated_dataset2['name']

    def test_handles_deleted_datasets(self):
        lc = LocalCKAN()
        lc.action.package_create(
            type="auto-create-valid-name", year="2020", location="north-pole"
        )
        dataset2 = lc.action.package_create(
            type="auto-create-valid-name", year="2020", location="north-pole"
        )
        lc.action.package_delete(id=dataset2['id'])

        dataset3 = lc.action.package_create(
            type="auto-create-valid-name", year="2020", location="north-pole"
        )
        assert dataset3['name'] == u'north-pole-autogenerate-2020-1'


@pytest.mark.usefixtures(u'clean_db')
@pytest.mark.usefixtures(u'clean_index')
class TestAutofill(object):
    def test_autofilling(self):
        lc = LocalCKAN()
        dataset = lc.action.package_create(
            type="autofill-validator", title="AutoFill", name='autofill', location="north-pole"
        )
        assert dataset['schema'] == u'art_3'
        assert dataset['dataset_type'] == u'data-type'
        assert dataset['year'] == u''

    def test_not_overwriting(self):
        lc = LocalCKAN()
        dataset = lc.action.package_create(
            type="autofill-validator", title="AutoFill", name='autofill', location="north-pole",
            schema="art_4", dataset_type="different-data-type", year="1984"
        )
        assert dataset['schema'] == u'art_4'
        assert dataset['dataset_type'] == u'different-data-type'
        assert dataset['year'] == u'1984'
