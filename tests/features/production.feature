Feature: Production readiness of the HR Assistant
  The API asks for a key per client, limits requests per minute and refuses to
  start in production with an insecure configuration. There is no open mode.

  Scenario: Ask and metrics need a valid key but the public routes do not
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 200
    When I ask "Who is EMP-0004?" without a key
    Then the response status is 401
    And the body detail is "invalid or missing API key"
    When I ask "Who is EMP-0004?" with the key "wrong-key-0000000000"
    Then the response status is 401
    And the body detail is "invalid or missing API key"
    When I request the metrics without a key
    Then the response status is 401
    When I request the metrics with the test key
    Then the response status is 200
    When I request "/health" without a key
    Then the response status is 200

  Scenario: Without API keys the API is closed even in development
    Given the environment is "development"
    And no API keys are configured
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 401
    When I request the metrics with the test key
    Then the response status is 401
    When I request "/" without a key
    Then the response status is 200
    When I request "/health" without a key
    Then the response status is 200
    When I request "/docs" without a key
    Then the response status is 200

  Scenario: The log names the client and never the key
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 200
    And the request event in the log has the client "hr-tester"
    And the agent_run and audit events have the client "hr-tester"
    And the log does not contain the test key

  Scenario: The request after the limit gets a 429 until the clock moves on
    Given the rate limit is 2 per minute
    And the clock is fake
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 200
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 200
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 429
    And the body detail is "rate limit exceeded"
    And the Retry-After header is a whole number of seconds
    When the clock advances 61 seconds
    And I ask "Who is EMP-0004?" with the test key
    Then the response status is 200

  Scenario: One client that used its limit does not affect another client
    Given the rate limit is 1 per minute
    And the clock is fake
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 200
    When I ask "Who is EMP-0004?" with the test key
    Then the response status is 429
    When I ask "Who is EMP-0004?" with the other key
    Then the response status is 200

  Scenario: Production refuses to start with the public example key
    Given the production settings
    And the environment variable API_KEYS is "demo:demo-example-key-0000"
    When I start the app
    Then startup is refused naming the rule "example_api_key"
    And the error does not contain "demo-example-key-0000"

  Scenario: Production starts with a correct configuration
    Given the production settings
    When I start the app
    Then the app starts

  Scenario: A malformed API_KEYS stops startup without showing the value
    Given the environment variable API_KEYS is "demo:good-key-0000000000,BROKENSECRETENTRY"
    When I start the app
    Then startup is refused mentioning "API_KEYS"
    And the error names entry 2 and length 17
    And the error does not contain "BROKENSECRETENTRY"

  Scenario: The page asks for the key and keeps it only in the session
    When I request "/" without a key
    Then the response status is 200
    And the page has a password field with the test id "api-key"
    And the page uses sessionStorage and never localStorage
