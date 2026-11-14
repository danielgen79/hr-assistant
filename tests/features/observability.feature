Feature: Observability of every request
  Support must be able to answer what happened with any request.

  Scenario: A request without an id gets a generated one
    When I ask "Who is EMP-0004?" without a request id
    Then the response header carries a generated UUID
    And the response body carries the same request id

  Scenario: A client request id is kept
    When I ask "Who is EMP-0004?" with the request id "demo-123"
    Then the response header request id is "demo-123"
    And the response body carries the same request id

  Scenario: A request leaves one request log line
    When I request the health endpoint with the request id "health-1"
    Then the log has a request event for "GET" "/health" with status 200
    And that event has a latency and the request id "health-1"

  Scenario: A question leaves an agent run and an audit line without text
    When I ask "Who is EMP-0004?" with the request id "ask-1"
    Then the log has one agent_run event with one step and the tool "get_employee"
    And the log has one audit event for the tool "get_employee"
    And the log does not contain the question or the answer

  Scenario: An internal failure is reported safely
    Given the model fails with an unexpected error
    When I ask "Who is EMP-0004?" with the request id "boom-1"
    Then the response status is 500
    And the body says "internal error" with the request id "boom-1"
    And the log has an error event with only the error type

  Scenario: Metrics summarize the requests of the process
    When I ask 3 questions
    And I request the metrics
    Then the metrics show 3 requests and positive tokens
    And the service level objective is met

  Scenario: A very low latency target is not met
    Given the latency target is 1 millisecond and the model is slow
    When I ask 2 questions
    And I request the metrics
    Then the service level objective is not met

  Scenario: The home page shows the request id
    When I request the home page
    Then the page mentions "request_id"

  Scenario: The product works without a LangSmith key
    Given LangSmith cannot be imported
    When I ask "Who is EMP-0004?" without a request id
    Then the response status is 200
