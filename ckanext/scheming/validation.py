import json
import datetime
from collections import defaultdict
import itertools
import pytz
import six
import ckan.lib.helpers as h
from ckan.lib.navl.dictization_functions import convert
from ckantoolkit import (
    get_validator,
    UnknownValidator,
    missing,
    Invalid,
    _
)
import ckantoolkit as t
import copy
import ckanext.scheming.helpers as sh
from ckanext.scheming.errors import SchemingException
from ckan.logic.validators import package_name_validator
import slugify

OneOf = get_validator('OneOf')
ignore_missing = get_validator('ignore_missing')
not_empty = get_validator('not_empty')

all_validators = {}


def validator(fn):
    """
    collect helper functions into ckanext.scheming.all_helpers dict
    """
    all_validators[fn.__name__] = fn
    return fn


def scheming_validator(fn):
    """
    Decorate a validator that needs to have the scheming fields
    passed with this function. When generating navl validator lists
    the function decorated will be called passing the field
    and complete schema to produce the actual validator for each field.
    """
    fn.is_a_scheming_validator = True
    validator(fn)
    return fn


@scheming_validator
def composite_form(field, schema):
    """
    A special validator used to collect and pack composite & repeating fields.
    """
    from ckanext.scheming.plugins import _field_create_validators

    def composite_validator(key, data, errors, context):
        # If the field is coming from the API the value will be set directly.
        value = data.get(key)
        if not value:
            # ... otherwise, it's a form submission so our values are stuck
            # unrolled in __extras.
            # If we're working on a package field, the key will look like:
            #   (<field name>,)
            # and if we're working on a resource it'll be:
            #   ('resources', <resource #>, <field name>)
            prefix = key[-1] + '-'
            _extras = data.get(key[:-1] + ('__extras',), {})

            # Group our unrolled fields by their index.
            values = defaultdict(dict)
            for k in _extras.keys():
                if k.startswith(prefix):
                    name = k[len(prefix):]
                    index, name = name.split('-', 1)
                    # Always pop, we don't want handled values to remain in
                    # __extras or they'll end up on the model.
                    values[int(index)][name] = _extras.pop(k)

            # ... then turn it back into an ordered list.
            value = [v for k, v in sorted(values.items())]

        elif isinstance(value, six.string_types):
            value = json.loads(value)

        if not isinstance(value, list):
            # We treat all composite fields as repeatable when processing, even
            # when they aren't defined that way in the schema.
            value = [value]

        for subfield in field['subfields']:
            validators = _field_create_validators(subfield, schema, False)
            for entry in value:
                # This right here is why we recommend globally unique field
                # names, else you risk trampling values from the top-level
                # schema. Some validators like require_when_published require
                # other top-level fields.
                entry_as_data = {(k,): v for k, v in entry.items()}
                entry_as_data.update(data)

                entry_errors = defaultdict(list)

                for v in validators:
                    convert(
                        v,
                        (subfield['field_name'],),
                        entry_as_data,
                        entry_errors,
                        context
                    )

                # Any subfield errors should be added as errors to the parent
                # since this is the only way we have to let other plugins know
                # of issues.
                errors[key].extend(
                    itertools.chain.from_iterable(
                        v for v in entry_errors.itervalues()
                    )
                )

                # Pull our potentially modified fields back. What if validators
                # modified other fields such as a top-level field? Is this
                # "allowed" in CKAN validators? We might have to replace
                # entry_as_data with a write-tracing dict to capture all
                # changes.
                for k in entry.keys():
                    entry[k] = entry_as_data[(k,)]

        # It would be preferable to just always store as a list, but some plugins
        # such as ckanext-restricted make assumptions on how ckanext-composite
        # stored its values.

        if field.get('repeatable', False):
            data[key] = json.dumps(value)
        elif value:
            data[key] = json.dumps(value[0])

    return composite_validator


@scheming_validator
def composite_display(field, schema):
    def composite_display(key, data, errors, context):
        pass

    return composite_display


@scheming_validator
def scheming_choices(field, schema):
    """
    Require that one of the field choices values is passed.
    """
    if 'choices' in field:
        return OneOf([c['value'] for c in field['choices']])

    def validator(value):
        if value is missing or not value:
            return value
        choices = sh.scheming_field_choices(field)
        for choice in choices:
            if value == choice['value']:
                return value
        raise Invalid(_('unexpected choice "{value}"').format(value))

    return validator


@scheming_validator
def scheming_required(field, schema):
    """
    not_empty if field['required'] else ignore_missing
    """
    if field.get('required'):
        return not_empty
    return ignore_missing


@scheming_validator
def scheming_multiple_choice(field, schema):
    """
    Accept zero or more values from a list of choices and convert
    to a json list for storage:

    1. a list of strings, eg.:

       ["choice-a", "choice-b"]

    2. a single string for single item selection in form submissions:

       "choice-a"
    """
    static_choice_values = None
    if 'choices' in field:
        static_choice_order = [c['value'] for c in field['choices']]
        static_choice_values = set(static_choice_order)

    def validator(key, data, errors, context):
        # if there was an error before calling our validator
        # don't bother with our validation
        if errors[key]:
            return

        value = data[key]
        if value is not missing:
            if isinstance(value, six.string_types):
                value = [value]
            elif not isinstance(value, list):
                errors[key].append(_('expecting list of strings'))
                return
        else:
            value = []

        choice_values = static_choice_values
        if not choice_values:
            choice_order = [
                choice['value']
                for choice in sh.scheming_field_choices(field)
            ]
            choice_values = set(choice_order)

        selected = set()
        for element in value:
            if element in choice_values:
                selected.add(element)
                continue
            errors[key].append(_('unexpected choice "{element}"').format(element))

        if not errors[key]:
            data[key] = json.dumps([
                v for v in
                (static_choice_order if static_choice_values else choice_order)
                if v in selected
            ])

            if field.get('required') and not selected:
                errors[key].append(_('Select at least one'))

    return validator


def validate_date_inputs(field, key, data, extras, errors, context):
    date_error = _('Date format incorrect')
    time_error = _('Time format incorrect')

    date = None

    def get_input(suffix):
        inpt = key[0] + '_' + suffix
        new_key = (inpt,) + tuple(x for x in key if x != key[0])
        key_value = extras.get(inpt)
        data[new_key] = key_value
        errors[new_key] = []

        if key_value:
            del extras[inpt]

        if field.get('required'):
            not_empty(new_key, data, errors, context)

        return new_key, key_value

    date_key, value = get_input('date')
    value_full = ''

    if value:
        try:
            value_full = value
            date = h.date_str_to_datetime(value)
        except (TypeError, ValueError):
            errors[date_key].append(date_error)

    time_key, value = get_input('time')
    if value:
        if not value_full:
            errors[date_key].append(
                _('Date is required when a time is provided'))
        else:
            try:
                value_full += ' ' + value
                date = h.date_str_to_datetime(value_full)
            except (TypeError, ValueError):
                errors[time_key].append(time_error)

    tz_key, value = get_input('tz')
    if value:
        if value not in pytz.all_timezones:
            errors[tz_key].append('Invalid timezone')
        else:
            if isinstance(date, datetime.datetime):
                date = pytz.timezone(value).localize(date)

    return date


@scheming_validator
def scheming_isodatetime(field, schema):
    def validator(key, data, errors, context):
        value = data[key]
        date = None

        if value:
            if isinstance(value, datetime.datetime):
                return value
            else:
                try:
                    date = h.date_str_to_datetime(value)
                except (TypeError, ValueError):
                    raise Invalid(_('Date format incorrect'))
        else:
            extras = data.get(('__extras',))
            if not extras or (key[0] + '_date' not in extras and
                              key[0] + '_time' not in extras):
                if field.get('required'):
                    not_empty(key, data, errors, context)
            else:
                date = validate_date_inputs(
                    field, key, data, extras, errors, context)

        data[key] = date

    return validator


@scheming_validator
def scheming_isodatetime_tz(field, schema):
    def validator(key, data, errors, context):
        value = data[key]
        date = None

        if value:
            if isinstance(value, datetime.datetime):
                date = sh.scheming_datetime_to_utc(value)
            else:
                try:
                    date = sh.date_tz_str_to_datetime(value)
                except (TypeError, ValueError):
                    raise Invalid(_('Date format incorrect'))
        else:
            extras = data.get(('__extras',))
            if not extras or (key[0] + '_date' not in extras and
                              key[0] + '_time' not in extras):
                if field.get('required'):
                    not_empty(key, data, errors, context)
            else:
                date = validate_date_inputs(
                    field, key, data, extras, errors, context)
                if isinstance(date, datetime.datetime):
                    date = sh.scheming_datetime_to_utc(date)

        data[key] = date

    return validator


@scheming_validator
def restricted_json(field, schema):
    def validator(key, data, errors, context):
        extra = data.get(key[:-1] + ('__extras',), {})
        value = {
            "level": extra.get("restricted_level", ""),
            "allowed_users": extra.get("restricted_allowed_users", ""),
            "allowed_organizations": extra.get("restricted_allowed_orgs", "")
        }
        data[key] = json.dumps(value)
    return validator


@validator
def scheming_valid_json_object(value, context):
    """Store a JSON object as a serialized JSON string

    It accepts two types of inputs:
        1. A valid serialized JSON string (it must be an object or a list)
        2. An object that can be serialized to JSON

    """
    if not value:
        return
    elif isinstance(value, six.string_types):
        try:
            loaded = json.loads(value)

            if not isinstance(loaded, dict):
                raise Invalid(
                    _('Unsupported value for JSON field: {}').format(value)
                )

            return value
        except (ValueError, TypeError) as e:
            raise Invalid(_('Invalid JSON string: {}').format(e))

    elif isinstance(value, dict):
        try:
            return json.dumps(value)
        except (ValueError, TypeError) as e:
            raise Invalid(_('Invalid JSON object: {}').format(e))
    else:
        raise Invalid(
            _('Unsupported type for JSON field: {}').format(type(value))
        )


@validator
def scheming_load_json(value, context):
    if isinstance(value, six.string_types):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


@validator
def scheming_multiple_choice_output(value):
    """
    return stored json as a proper list
    """
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return [value]


def validators_from_string(s, field, schema):
    """
    convert a schema validators string to a list of validators

    e.g. "if_empty_same_as(name) unicode" becomes:
    [if_empty_same_as("name"), unicode]
    """
    out = []
    parts = s.split()
    for p in parts:
        if '(' in p and p[-1] == ')':
            name, args = p.split('(', 1)
            args = args[:-1].split(',')  # trim trailing ')', break up
            v = get_validator_or_converter(name)(*args)
        else:
            v = get_validator_or_converter(p)
        if getattr(v, 'is_a_scheming_validator', False):
            v = v(field, schema)
        out.append(v)
    return out


def get_validator_or_converter(name):
    """
    Get a validator or converter by name
    """
    if name == 'unicode':
        return six.text_type
    try:
        v = get_validator(name)
        return v
    except UnknownValidator:
        pass
    raise SchemingException('validator/converter not found: %r' % name)
