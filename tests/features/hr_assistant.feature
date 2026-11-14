Feature: HR Assistant answers questions about employees
  HR staff ask questions and the agent answers using the employee directory.

  Scenario: Ask about an existing employee
    When I ask "Who is EMP-0004?"
    Then the response status is 200
    And the answer mentions "Jorge Díaz"
    And the tools used are "get_employee"
    And the agent took 2 steps

  Scenario: Ask about an unknown employee
    When I ask "Who is EMP-9999?"
    Then the response status is 200
    And the answer mentions "EMP-9999"
    And the answer says the employee does not exist

  Scenario: List a department
    When I ask "Who works in Finanzas?"
    Then the response status is 200
    And the answer mentions "Sofía Gómez"
    And the tools used are "search_by_department"

  Scenario: Ask without an id or a department
    When I ask "Hello there"
    Then the response status is 200
    And the answer mentions "Pregúntame por un empleado (EMP-0001) o un departamento."
    And no tools were used

  Scenario: Empty question is rejected
    When I ask an empty question
    Then the response status is 422

  Scenario: Question that is too long is rejected
    When I ask a question longer than the limit
    Then the response status is 422

  Scenario: History sent by the client is accepted and not stored
    When I ask "Who is EMP-0001?" with a previous conversation
    Then the response status is 200
    And the same question without history gives the same answer

  Scenario: Step limit stops the agent
    Given the agent is limited to 1 step
    When I ask "Who is EMP-0004?"
    Then the response status is 200
    And the answer is the step limit message
    And the agent took 1 steps

  Scenario: Health check reports the process
    When I request the health endpoint
    Then the response status is 200
    And the health body has status "ok" and a numeric pid

  Scenario: Home page has the test ids
    When I request the home page
    Then the response status is 200
    And the page contains the test ids "question", "send" and "answer"
