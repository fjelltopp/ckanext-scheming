# -*- coding: utf-8 -*-
import datetime
import pycountry
import logging
import ckanext.scheming.helpers as helpers
from ckanapi import NotFound
from ckan.plugins.toolkit import get_action
import ckan.model as model
from ckan.common import g


@helpers.helper
def get_date():
    """
    Returns the current date.
    """
    return datetime.datetime.now()


@helpers.helper
def get_user(user_id):
    """
    Returns the user object for a given user_id.
    """
    context = {'model': model, 'user': g.user}
    try:
        result = get_action('user_show')(context, {'id': user_id})
        return result
    except Exception:
        logging.warning("Failed to get user dict for user_id: {}".format(user_id))
        return {}


@helpers.helper
def get_missing_resources(pkg, schema):
    """
    Identify which pre-specified resources are defined in the package
    schema but currently missing from the actual package. Return the
    details of those missing resources. A pre-specified resource is
    defined in the package schema e.g a HIVE package should contain ART
    data, ANC data and SVY data.
    """
    pkg_res = [r['resource_type'] for r in pkg.get('resources', [])]

    ret = []
    for r in schema.get('resources', []):
        resource_type_ = r['resource_type']
        if resource_type_ not in pkg_res:
            if include_vmmc_resources(pkg, resource_type_):
                ret.append(r)

    return ret


def include_vmmc_resources(pkg, resource_type):
    vmmc_countries = [
        "Botswana",
        "Eswatini",
        "Ethiopia",
        "Kenya",
        "Lesotho",
        "Malawi",
        "Mozambique",
        "Namibia",
        "Rwanda",
        "South Africa",
        "South Sudan",
        "Tanzania",
        "Uganda",
        "Zambia",
        "Zimbabwe"
    ]
    vmmc_resource_types = ['inputs-unaids-vmmc-coverage-inputs', 'inputs-unaids-vmmc-coverage-outputs']
    country_ = pkg.get('geo-location')
    if resource_type in vmmc_resource_types and country_ not in vmmc_countries:
        return False
    else:
        return True


@helpers.helper
def scheming_country_list():
    """
    Returns a list of all countries taken from pycountry
    """
    countries = [{"text": "", "value": ""}]
    for country in pycountry.countries:
        countries.append({
            "text": country.name,
            "value": country.name
        })
    countries.append({
        "text": "Zanzibar",
        "value": "Zanzibar"
    })
    return sorted(countries, key=lambda k: k['value'])


@helpers.helper
def scheming_resource_view_get_fields(resource):
    '''Returns sorted list of text and time fields of a datastore resource.'''

    if not resource.get('datastore_active'):
        return []

    data = {
        'resource_id': resource['id'],
        'limit': 0
    }
    try:
        result = get_action('datastore_search')({}, data)
    except NotFound:
        return []
    fields = [field['id'] for field in result.get('fields', [])]

    return sorted(fields)


@helpers.helper
def get_resource_field(dataset_type, resource_type, field_name):
    """
    Return the field for a particular resource type in a particular package
    type.
    """
    try:
        schema = helpers.scheming_get_dataset_schema(dataset_type)
        resource = filter(
            lambda x: x.get('resource_type') == resource_type,
            schema.get('resources', [])
        )[0]
        fields = resource.get('resource_fields') + schema.get('resource_fields', [])
        field = filter(
            lambda x: x.get('field_name') == field_name,
            fields
        )[0]
        return field
    except IndexError:
        return {}


def comma_swap_formatter(input):
    """
    Swaps the parts of a string around a single comma.
    Use to format e.g. "Tanzania, Republic of" as "Republic of Tanzania"
    """
    if input.count(',') == 1:
        parts = input.split(',')
        stripped_parts = list(map(lambda x: x.strip(), parts))
        reversed_parts = reversed(stripped_parts)
        joined_parts = " ".join(reversed_parts)
        return joined_parts
    else:
        return input


def lower_formatter(input):
    return input.lower()
