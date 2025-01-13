# GitHub Copilot Prompts

Make sure to:

- select the code that you want to test. The prompt specifies the name of the file and the function to be tested (this redundancy is needed)
- open tabs with relevant files for the tests, for example: `conftest.py`, `test_auth.py`. This helps Copilot with context.

## Examples

### Create Comprehensive suite of unit tests

@workspace /tests Develop a comprehensive suite of unit tests for the selected code (only the function (only the function api_create_user_api_token in auth_api.py file) in auth_api.py file).
Requirements:

- use register endpoint to obtain the access token (see example in test_register_ok)
- write multiple test functions that cover a wide range of scenarios, including the succes flow, edge cases, exception handling, and data validation
- for the success case create a new ACL before creating the token

### Create tests for a particular usecase

@workspace /tests Develop a test for the selected code (only the function api_get_user_acls in auth_api.py file).
Requirements:

- use register endpoint to obtain the access token (see example in test_register_ok)
- the test should only check that the ACLs are sorted alphabeticaly by name
