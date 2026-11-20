Feature: The agent works with a model that behaves like a real one
  A real model wraps its JSON in code blocks, writes text before it, or
  invents data after calling a tool. The agent must still answer from the
  directory and must never leak its system message.

  Scenario: The model wraps its JSON in a code block
    Given a model that answers inside a code block
    When I ask "Who is EMP-0004?" to that model
    Then the response status is 200
    And the tools used are "get_employee"
    And the answer comes from the directory and mentions "Jorge Díaz"

  Scenario: The model writes text before its JSON
    Given a model that writes text before the JSON
    When I ask "Who is EMP-0004?" to that model
    Then the tools used are "get_employee"
    And the answer comes from the directory and mentions "Jorge Díaz"

  Scenario: The model invents an answer after the tool call
    Given a model that returns the tool call followed by an invented answer
    When I ask "Who is EMP-0004?" to that model
    Then the tools used are "get_employee"
    And the answer comes from the directory and mentions "Jorge Díaz"
    And the answer does not contain the invented text

  Scenario: The model answers with plain text and no JSON
    Given a model that answers with plain text only
    And the agent is limited to 2 steps
    When I ask "Who is EMP-0004?" to that model
    Then the response status is 200
    And the answer is the step limit message
    And the agent took 2 steps

  Scenario: The simulated model answers as before
    When I ask "¿Quién es EMP-0004?" to the simulated model
    Then the tools used are "get_employee"
    And the answer comes from the directory and mentions "Jorge Díaz"

  Scenario: The system message never reaches the response or the log
    Given a model that answers inside a code block
    When I ask "Who is EMP-0004?" to that model
    Then the system message is not in the response
    And the system message is not in the log
