Feature: Sensitive data under control
  Personal data must never reach the model, the log or the response.

  Scenario: An email in the question is masked and counted
    Given a model that answers "Done"
    When I ask "Who is EMP-0004? My email is ana.perez@example.com"
    Then the response status is 200
    And the report counts 1 "email"
    And the model never received "ana.perez@example.com"
    And the response and the log never contain "ana.perez@example.com"

  Scenario: Block mode rejects sensitive data without calling the model
    Given a model that answers "Done"
    And the sensitive data mode is "block"
    When I ask "Who is EMP-0004? My email is ana.perez@example.com"
    Then the response status is 422
    And the error lists the type "email" and a request id
    And the model was not called
    And the response and the log never contain "ana.perez@example.com"

  Scenario: A sensitive answer is masked even in block mode
    Given a model that answers "Write to ana.perez@example.com"
    And the sensitive data mode is "block"
    When I ask "Who is EMP-0004?"
    Then the response status is 200
    And the answer is "Write to [EMAIL]"
    And the report counts 1 "email"

  Scenario: A history over the limit is rejected
    Given a model that answers "Done"
    And the history limit is 3 messages
    When I ask "Who is EMP-0004?" with a history of 4 messages
    Then the response status is 422
    And the model was not called

  Scenario: Twenty simultaneous questions keep their own request id
    Given a model that answers "Done"
    When I send 20 simultaneous questions with distinct request ids
    Then every response is 200 and carries its own request id
