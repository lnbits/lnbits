# GitHub Copilot Prompts

Make sure to:

- select the code that you want to test. The prompt specifies the name of the file and the function to be tested (this redundancy is needed)
- open tabs with relevant files for the tests, for example: `conftest.py`, `test_auth.py`. This helps Copilot with context.

## Examples

### Create Comprehensive suite of unit tests

_Sample 1_
@workspace /tests Develop a comprehensive suite of unit tests for the selected code (only the function (only the function api_create_user_api_token in auth_api.py file) in auth_api.py file).
Requirements:

- use register endpoint to obtain the access token (see example in test_register_ok)
- write multiple test functions that cover a wide range of scenarios, including the succes flow, edge cases, exception handling, and data validation
- for the success case create a new ACL before creating the token

_Sample 2_
@workspace /tests Develop a comprehensive suite of unit tests for the selected code (only the function check_user_exists in decorators.py file) .
Requirements:

- write multiple test functions that cover a wide range of scenarios, including the succes flow, edge cases, security vulnerabilities, exception handling, and data validation
- use the login endpoint to obtain a valid access token. Use the `user_alan: User` fixture for the login params. Check the `test_login_alan_username_password_ok` function in the `test_auth.py` file as an example for login.
- do not use mocks. For the request parameter initialize the fastapi.Request class.
- make sure to cover all if-then-else branches

### Create tests for a particular usecase

_Sample 1_
@workspace /tests Develop a test for the selected code (only the function api_get_user_acls in auth_api.py file).
Requirements:

- use register endpoint to obtain the access token (see example in test_register_ok)
- the test should only check that the ACLs are sorted alphabeticaly by name

_Sample 1_
@workspace /tests Develop a test for the selected code (only the function check_user_exists in decorators.py file).
Requirements:

- use register endpoint to obtain the access token (see example in the file test_auth.py the function test_register_ok())
- the test should register a new user, obtain the access token then delete the user. Then check that check_user_exists() fails as expected

@workspace /tests Develop a test for the selected code (only the function check_user_exists in decorators.py file).
Requirements:

- check only the branch where user_id_only login is allowed
