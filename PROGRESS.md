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
✓ RESOLVED - Major success! All validator errors are now fixed.

**Test Results:**
- CKAN 2.11: 11 failed, 146 passed (93% pass rate - up from 87%)
- CKAN 2.10: 6 failed, 151 passed (96% pass rate - up from 90%)

All remaining failures are form rendering issues in `test_form.py`, not validator errors. The core Python 3.10 and CKAN 2.11 compatibility for validators is complete!

---

## Issue 9: Form rendering issues - missing form fields

**Date:** 2025-12-24

**Problem:**
After fixing all validator issues, 11 tests still fail in CKAN 2.11 and 6 tests in CKAN 2.10. All failures are in `test_form.py` and related to form rendering:

**CKAN 2.11 failures (11):**
1. `test_resource_form_includes_custom_fields` - AttributeError: 'NoneType' object has no attribute 'select'
2. `test_organization_form_includes_custom_field` - assert []
3. `test_group_form_includes_custom_field` - assert []
4. `test_custom_group_form_includes_custom_field` - assert []
5. `test_org_form_includes_custom_field` - assert []
6. `test_dataset_form_includes_json_fields` - assert []
7. `test_dataset_form_create` - ckan.logic.NotFound
8. `test_dataset_form_update` - AssertionError: assert {'a': 1, 'b': 2} == {'a': 1, 'b': 2, 'c': 3}
9. `test_resource_form_includes_json_fields` - AttributeError: 'NoneType' object has no attribute 'select'
10. `test_resource_form_create` - IndexError: list index out of range
11. `test_resource_form_update` - AttributeError: 'NoneType' object has no attribute 'select_one'

**CKAN 2.10 failures (6):**
All of the above except items 2-6 (which only fail in CKAN 2.11).

**Root Cause:**
The test failures were caused by missing asset files and configuration. The error logs showed:
```
Cannot create library scheming at .../ckanext/scheming/fanstatic because webassets.yaml is missing
Trying to include unknown asset: <ckanext-scheming/scheming_css>
404 Not Found on URLs like /dataset/new_resource/{id}
```

CKAN 2.10+ uses webassets instead of fanstatic for asset management. The current code was still using the old fanstatic approach:
1. `plugins.py:161` had `add_resource('fanstatic', 'scheming')` instead of `add_resource('assets', 'ckanext-scheming')`
2. No `assets/` directory with the required `webassets.yml` configuration file
3. No `base.html` template to include the CSS assets
4. No `scheming_asset.html` snippet referenced by base.html

This caused pages to return 404 errors because the assets couldn't be loaded properly.

**Solution:**
Migrated from fanstatic to webassets by copying asset files from upstream (DONT/):
1. Copied entire `assets/` directory containing:
   - `webassets.yml` - Defines scheming_css, subfields, and multiple_text assets
   - `styles/scheming.css` - Scheming CSS styles
   - `js/scheming-repeating-subfields.js` - JavaScript for repeating subfields
   - `js/scheming-multiple-text.js` - JavaScript for multiple text fields
2. Updated `plugins.py:161` to use `add_resource('assets', 'ckanext-scheming')` instead of `add_resource('fanstatic', 'scheming')`
3. Copied `templates/base.html` to extend CKAN's base template and include scheming assets
4. Copied `templates/scheming/snippets/scheming_asset.html` that loads the scheming_css asset

**Files Modified:**
- `ckanext/scheming/plugins.py` - Changed add_resource call from fanstatic to assets (line 161)

**Files Added:**
- `ckanext/scheming/assets/webassets.yml` - NEW FILE
- `ckanext/scheming/assets/styles/scheming.css` - NEW FILE
- `ckanext/scheming/assets/js/scheming-repeating-subfields.js` - NEW FILE
- `ckanext/scheming/assets/js/scheming-multiple-text.js` - NEW FILE
- `ckanext/scheming/assets/resource.config` - NEW FILE
- `ckanext/scheming/templates/base.html` - NEW FILE
- `ckanext/scheming/templates/scheming/snippets/scheming_asset.html` - NEW FILE

**Result:**
✓ PARTIALLY RESOLVED - Asset configuration migrated to webassets. The webassets errors are gone, but tests still showed 404 errors. Further investigation revealed the root cause: test file was using old CKAN 2.8 URL patterns and authentication methods.

---

## Issue 10: Test file using deprecated CKAN 2.8 URL patterns and authentication

**Date:** 2025-12-24

**Problem:**
After fixing assets (Issue #9), tests still failed with 404 errors. The asset-related errors were gone, but forms were still not loading.

Investigation revealed the test file `test_form.py` was using:
- Old URL patterns from CKAN 2.8:
  - `/dataset/new_resource/{id}` → should be `/dataset/{id}/resource/new`
  - `/dataset/{id}/resource_edit/{resource_id}` → should be `/dataset/{id}/resource/{resource_id}/edit`
- Old authentication method: `extra_environ` instead of `headers` for CKAN 2.10+
- Direct `app.get()` calls instead of version-aware helper functions
- Missing `sysadmin_env` parameters in some tests

**Root Cause:**
The test file hadn't been updated for CKAN 2.9+ changes:
1. CKAN 2.9 migrated from Pylons to Flask, changing URL patterns
2. CKAN 2.10 changed authentication from `extra_environ` to `headers`
3. CKAN 2.10 introduced `SysadminWithToken` factory instead of `Sysadmin`

**Solution:**
Updated `test_form.py` with CKAN 2.10/2.11 compatible test helpers from upstream:
1. Added version-aware helper functions that check CKAN version:
   - `_get_resource_new_page()` - uses correct URL format
   - `_get_resource_update_page()` - uses correct URL format
   - `_get_package_new_page()` - uses correct URL format
   - `_get_package_update_page()` - uses correct URL format
   - `_get_organization_new_page()` - uses correct URL format
   - `_get_group_new_page()` - uses correct URL format
   - `_post_data()` - handles both headers and extra_environ based on version
2. Updated `sysadmin_env` fixture to use `SysadminWithToken` for CKAN 2.10+ with fallback
3. Updated all test methods to use sysadmin_env parameter and helper functions
4. Fixed imports to use `ckan.tests.factories` instead of `ckantoolkit.tests.factories`
5. Changed `ckantoolkit.h.url_for` to `h.url_for` (imported from toolkit)
6. Added helper functions `_get_organization_form()` and `_get_group_form()`

**Files Modified:**
- `ckanext/scheming/tests/test_form.py` - Complete rewrite of helper functions and test methods (lines 1-430, plus lines 240, 263, 281 for check_ckan_version fixes)

**Result:**
✓ PARTIALLY RESOLVED - All test helper functions updated for CKAN 2.10/2.11 compatibility. Tests now use correct URL patterns and authentication methods.

After testing:
- CKAN 2.11: 11→5 failures (97% pass rate)
- CKAN 2.10: All tests passed (100% pass rate)

Remaining 5 failures in CKAN 2.11 were due to incorrect form selectors (see Issue 11).

**Note:** Fixed lint error by replacing remaining `ckantoolkit.check_ckan_version()` calls with `check_ckan_version()` (already imported from ckan.plugins.toolkit).

---

## Issue 11: Wrong form selectors in organization and group tests

**Date:** 2025-12-24

**Problem:**
After fixing Issue #10, 5 tests still failed in CKAN 2.11 (all passed in CKAN 2.10):
1. `test_organization_form_includes_custom_field` - assert []
2. `test_group_form_includes_custom_field` - assert []
3. `test_custom_group_form_includes_custom_field` - assert []
4. `test_org_form_includes_custom_field` - assert []
5. `test_dataset_form_includes_json_fields` - assert []

All failures were assertions that expected to find form fields, but found empty lists instead.

**Root Cause:**
Investigation revealed the tests were using **wrong form selectors**:
- Current (broken): `form = BeautifulSoup(response.body).select("form")[1]`
- DONT (working): `form = BeautifulSoup(response.body).select("#dataset-edit")[0]`

The positional selector `select("form")[1]` was selecting the **search form** instead of the **edit form** on the page. This is why the custom fields weren't found - they were looking in the wrong form element.

Additionally, some test methods weren't using the proper sysadmin_env fixture parameter, instead calling `_get_*_page_as_sysadmin()` helper functions which duplicated authentication setup.

**Solution:**
Fixed all 5 failing tests by updating form selectors and authentication:

1. **test_organization_form_includes_custom_field** (line 219):
   - Changed from `_get_organization_new_page_as_sysadmin(app)` to `_get_organization_new_page(app, sysadmin_env)`
   - Changed from `select("form")[1]` to `_get_organization_form(response.body)` helper

2. **test_group_form_includes_custom_field** (line 242):
   - Changed from `_get_group_new_page_as_sysadmin(app)` to `_get_group_new_page(app, sysadmin_env)`
   - Changed from `select("form")[1]` to `_get_group_form(response.body)` helper

3. **test_custom_group_form_includes_custom_field** (line 265):
   - Changed from `_get_group_new_page_as_sysadmin(app, type="theme")` to `_get_group_new_page(app, sysadmin_env, type="theme")`
   - Changed from `select("form")[1]` to `_get_group_form(response.body)` helper

4. **test_org_form_includes_custom_field** (line 283):
   - Changed from `_get_organization_new_page_as_sysadmin(app, type="publisher")` to `_get_organization_new_page(app, sysadmin_env, type="publisher")`
   - Changed from `select("form")[1]` to `_get_organization_form(response.body)` helper

5. **test_dataset_form_includes_json_fields** (line 299):
   - Changed from `_get_package_new_page_as_sysadmin(app)` to `_get_package_new_page(app, sysadmin_env)`
   - Changed from `select("form")[1]` to `select("#dataset-edit")[0]`

**Files Modified:**
- `ckanext/scheming/tests/test_form.py` - Updated 5 test methods to use correct form selectors (lines 219-225, 242-248, 265-268, 283-287, 299-302)

**Result:**
✓ TO BE TESTED - All 5 failing tests have been fixed with correct form selectors. Tests should now achieve 100% pass rate in both CKAN 2.11 and CKAN 2.10.
