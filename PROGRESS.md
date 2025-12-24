# ckanext-scheming Migration Progress

## Issue 1: Missing pycountry dependency

**Date:** 2025-12-24

**Problem:**
Both CKAN 2.10 and CKAN 2.11 tests were failing during plugin loading with:
```
ModuleNotFoundError: No module named 'pycountry'
  File "/home/toavina/fjelltopp/adx/adx_develop/submodules/ckanext-scheming/ckanext/scheming/helpers.py", line 7, in <module>
    import pycountry
```

**Root Cause:**
The `helpers.py` file imports `pycountry` on line 7, but this dependency was not declared in the `install_requires` list in `setup.py`. The `install_requires` was an empty list `[]`, causing the module to not be installed when the extension was installed.

**Solution:**
Added `pycountry` to the `install_requires` list in `setup.py`.

**Files Modified:**
- `setup.py` - Added `pycountry` to the `install_requires` list (line 27-29)

**Result:**
✓ RESOLVED - Tests confirmed the pycountry import error is fixed.

---

## Issue 2: Missing ckanapi dependency

**Date:** 2025-12-24

**Problem:**
After fixing pycountry, both CKAN 2.10 and CKAN 2.11 tests now fail with:
```
ModuleNotFoundError: No module named 'ckanapi'
  File "/home/toavina/fjelltopp/adx/adx_develop/submodules/ckanext-scheming/ckanext/scheming/helpers.py", line 13, in <module>
    from ckanapi import LocalCKAN, NotFound, NotAuthorized
```

**Root Cause:**
The `helpers.py` file imports `ckanapi` on line 13, and it's also used throughout the codebase (logic.py, unaids_helpers.py, and test files), but this dependency was not declared in the `install_requires` list in `setup.py`.

**Solution:**
Added `ckanapi` to the `install_requires` list in `setup.py`.

**Files Modified:**
- `setup.py` - Added `ckanapi` to the `install_requires` list (line 27-30)

**Result:**
✓ RESOLVED - Tests confirmed the ckanapi import error is fixed.

---

## Issue 3: pytest incompatibility with Python 3.10

**Date:** 2025-12-24

**Problem:**
After fixing ckanapi, both CKAN 2.10 and CKAN 2.11 tests fail with:
```
TypeError: required field "lineno" missing from alias
  File "/usr/local/lib/python3.10/site-packages/_pytest/assertion/rewrite.py", line 406, in _rewrite_test
    co = compile(tree, fn.strpath, "exec", dont_inherit=True)
```

Also saw:
```
AttributeError: 'AssertionRewritingHook' object has no attribute 'find_spec'
```

**Root Cause:**
The `test-requirements.txt` specified `pytest==4.6.5` and `pytest-cov==2.7.1`, which are too old for Python 3.10. pytest 4.6.5 was released in 2019 and doesn't support the AST (Abstract Syntax Tree) changes introduced in Python 3.10. The error occurs during pytest's assertion rewriting phase when it tries to compile test files.

CKAN 2.11 itself uses pytest 7.4.4 (seen in test output), so we need to align with a pytest 7.x version for compatibility.

**Solution:**
Updated pytest versions in `test-requirements.txt`:
- `pytest==4.6.5` → `pytest>=7.0.0`
- `pytest-cov==2.7.1` → `pytest-cov>=3.0.0`

**Files Modified:**
- `test-requirements.txt` - Updated pytest and pytest-cov to versions compatible with Python 3.10

**Result:**
✓ RESOLVED - Tests confirmed pytest is now compatible. Tests are collecting: "collected 138 items".

---

## Issue 4: jinja2 Markup import incompatibility

**Date:** 2025-12-24

**Problem:**
After fixing pytest, test collection fails with:
```
ImportError: cannot import name 'Markup' from 'jinja2'
  File "ckanext/scheming/tests/test_form_snippets.py", line 4
    from jinja2 import Markup
```

**Root Cause:**
In jinja2 version 3.0+ (used by CKAN 2.11), the `Markup` class was moved from `jinja2` to the `markupsafe` package. The old import `from jinja2 import Markup` no longer works in jinja2 3.0+.

**Solution:**
Updated the import in `test_form_snippets.py` to use a try/except block that:
1. First tries to import from `markupsafe` (jinja2 3.0+)
2. Falls back to importing from `jinja2` (older versions)

This maintains compatibility with both old and new versions of jinja2.

**Files Modified:**
- `ckanext/scheming/tests/test_form_snippets.py` - Updated Markup import (lines 4-7)

**Result:**
✓ RESOLVED - Tests confirmed Markup import is fixed. Tests now running: collected 157 items.

---

## Issue 5: Validator type error - str cannot be used as validator

**Date:** 2025-12-24

**Problem:**
Tests are running but many fail with:
```
TypeError: str cannot be used as validator because it is not a user-defined function
```

This affects 79 tests in CKAN 2.11 and 74 tests in CKAN 2.10.

**Root Cause:**
In CKAN 2.11, validators must be actual function objects, not strings or types. The current code had three issues:

1. **Line 450**: `get_validator_or_converter` returned `six.text_type` (the `str` type in Python 3) for 'unicode', but CKAN 2.11 requires a validator function, not a type
2. **Missing import**: No `ast` module for proper argument parsing
3. **Argument parsing**: Used simple string split instead of `ast.literal_eval`, causing issues with complex validator arguments

**Solution:**
Applied minimal fixes from upstream (DONT/ directory) to current code:
1. Added `import ast` at the top of validation.py
2. Added `unicode_safe = get_validator('unicode_safe')` to get the actual validator function
3. Changed `get_validator_or_converter` to return `unicode_safe` instead of `six.text_type`
4. Updated `validators_from_string` to use `ast.literal_eval()` for robust argument parsing with fallback to simple split

**Files Modified:**
- `ckanext/scheming/validation.py` - Fixed validator resolution (lines 1, 23, 437-446, 452)

**Result:**
✓ PARTIALLY RESOLVED - Major improvement! CKAN 2.11: 79→20 failures, CKAN 2.10: 74→15 failures.
However, 8 tests still have validator errors in UNAIDS validators.

---

## Issue 6: Remaining validator errors in UNAIDS validators

**Date:** 2025-12-24

**Problem:**
After Issue #5 fix, 8 tests still fail with validator errors:
- test_organization_displays_custom_fields
- test_group_displays_custom_fields
- test_prevents_duplicates
- test_preserves_existing_dataset_name
- test_handles_deleted_datasets
- test_autofilling
- test_not_overwriting

**Root Cause:**
The `scheming_validator` decorator in `validation.py` was calling `validator(fn)`, which registered validators incorrectly. The UNAIDS validators import this decorator, causing issues.

In DONT/ (upstream), `scheming_validator` is in a separate `decorators.py` file and doesn't call `validator(fn)` - it only sets the flag `fn.is_a_scheming_validator = True`.

**Solution:**
1. Created new `ckanext/scheming/decorators.py` with the simpler `scheming_validator` decorator
2. Updated `unaids_validators.py` to import from `decorators` instead of `validation`
3. Updated `validation.py` to import `scheming_validator` from `decorators` and removed the local definition
4. Fixed bug in `auto_create_valid_name` validator: save `original_name` to avoid infinite loop with incrementing counters

**Files Modified:**
- `ckanext/scheming/decorators.py` - NEW FILE with scheming_validator decorator
- `ckanext/scheming/unaids_validators.py` - Updated import + fixed auto_create_valid_name bug (lines 2, 73, 81)
- `ckanext/scheming/validation.py` - Added import from decorators, removed local scheming_validator (lines 19, 29-34 removed)

**Result:**
✓ MAJOR IMPROVEMENT! Test pass rate: 87% (CKAN 2.11) and 90% (CKAN 2.10)

**Current Status:**
- CKAN 2.11: 20 failed, 137 passed (87% pass)
- CKAN 2.10: 15 failed, 142 passed (90% pass)

Remaining 20 failures appear to be:
- 8 tests: Still have validator errors (mostly in test schemas using 'str' or 'unicode' as converters)
- 12 tests: Form/display issues (missing form fields, assertion failures)

**Note:** User manually added `@pytest.mark.usefixtures(u'with_plugins')` to TestAutoCreateValidName and TestAutofill classes for test setup.

**Next Steps:**
The remaining failures may require:
1. Checking test schema files for deprecated validator names (unicode, str)
2. Investigating form rendering issues in CKAN 2.11
3. Individual test-by-test debugging

The core compatibility issues have been resolved!

---

## Issue 7: Schema files using deprecated 'unicode' validator

**Date:** 2025-12-24

**Problem:**
After Issue #6, 20 tests still failed (8 with validator errors). Investigation revealed that despite fixing `get_validator_or_converter()` in validation.py:448-449 to return `unicode_safe` when encountering 'unicode', the schema JSON files were directly using `"unicode"` as a validator name.

Error traceback showed: `converter = <class 'str'>` indicating the str class was still being used as a validator.

**Root Cause:**
All schema files (presets.json, group schemas, organization schemas, dataset schemas, and test schemas) were using the deprecated `"unicode"` validator name in their validator strings. In CKAN 2.11, validators must be actual function objects, not type classes.

The upstream DONT/ directory had already updated all these files to use `"unicode_safe"` instead of `"unicode"`.

**Solution:**
Updated all schema JSON files to replace `"unicode"` with `"unicode_safe"` in validator strings, matching the upstream changes.

**Files Modified:**
1. `ckanext/scheming/presets.json` - 6 replacements
2. `ckanext/scheming/group_with_bookface.json` - 2 replacements
3. `ckanext/scheming/custom_group_with_status.json` - 2 replacements
4. `ckanext/scheming/custom_org_with_address.json` - 2 replacements
5. `ckanext/scheming/org_with_dept_id.json` - 2 replacements
6. `ckanext/scheming/ckan_dataset.json` - 1 replacement
7. `ckanext/scheming/tests/schemas/autofill_validator.json` - 1 replacement
8. `ckanext/scheming/tests/schemas/auto_unique_validator.json` - 1 replacement

**Changes Made:**
All instances of:
```json
"validators": "... unicode ..."
```
Were changed to:
```json
"validators": "... unicode_safe ..."
```

**Result:**
✓ PARTIALLY RESOLVED - All schema files now use the CKAN 2.11-compatible `unicode_safe` validator function. However, tests still failed with the same error, revealing there was another source of the `str` class being used as a validator.

---

## Issue 8: Default validators using str type class in plugins.py

**Date:** 2025-12-24

**Problem:**
After Issue #7, tests still failed with the same error:
```
TypeError: str cannot be used as validator because it is not a user-defined function
converter = <class 'str'>, key = ('location',)
```

The error was occurring for fields that had NO validators specified in the schema (like the `location` field in test schemas).

**Root Cause:**
In `plugins.py` lines 567 and 569, the `_field_validators()` function was setting default validators for fields without explicit validators:
```python
elif helpers.scheming_field_required(f):
    validators = [not_empty, six.text_type]  # six.text_type is str class!
else:
    validators = [ignore_missing, six.text_type]  # six.text_type is str class!
```

`six.text_type` is the `str` class in Python 3, which cannot be used as a validator in CKAN 2.11. CKAN 2.11 requires validators to be actual function objects, not type classes.

**Solution:**
Removed `six.text_type` from the default validator lists in `_field_validators()`, matching the upstream DONT/ changes:
```python
elif helpers.scheming_field_required(f):
    validators = [not_empty]
else:
    validators = [ignore_missing]
```

**Files Modified:**
- `ckanext/scheming/plugins.py` - Removed `six.text_type` from default validators (lines 567, 569)

**Result:**
✓ TO BE TESTED - This is the actual root cause of the "str cannot be used as validator" errors. All fields without explicit validators will now only use `not_empty` or `ignore_missing` validators (actual functions), not the `str` type class.
