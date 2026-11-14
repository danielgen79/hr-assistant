Feature: Cost per answer
  The assistant routes each question to a small or a large model and reports
  what every answer costs, using the price of the model that answered.

  Scenario: A simple question goes to the small model
    When I ask "Who is EMP-0004?"
    Then the response status is 200
    And the response model is "@cf/meta/llama-3.1-8b-instruct-fast"
    And the route is "simple"
    And the cost matches the price of that model

  Scenario: A question that asks to compare goes to the large model
    When I ask "Compara a EMP-0001 con EMP-0002"
    Then the response status is 200
    And the response model is "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    And the route is "keyword"
    And the cost matches the price of that model

  Scenario: Turning routing off always uses the large model
    Given the environment variable ROUTING is "false"
    When I ask "Who is EMP-0004?"
    Then the response model is "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    And the route is "routing_disabled"

  Scenario: The metrics add up the cost of every answer
    When I ask "Who is EMP-0004?" and then "Who is EMP-0002?"
    And I request the metrics
    Then the metrics cost equals the sum of both answer costs

  Scenario: A model failure is reported as bad gateway
    Given the model is unavailable
    When I ask "Who is EMP-0004?"
    Then the response status is 502
    And the body says "model unavailable" with the request id of the response
