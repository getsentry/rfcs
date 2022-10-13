* Start Date: 2022-10-13
* RFC Type: informational
* RFC PR: https://github.com/getsentry/rfcs/pull/27

# Summary

flaky tests in `sentry` / `getsentry` significantly impact developer
productivity.  ideally an automated system would improve this situation but
in the interim this rfc aims to document a manual process for disabling
flaky tests.

# Motivation

currently any test flake will require the entire job to be rerun, which
usually wastes about ~20 minutes of developer time per test flake.

to minimize disruptiveness, this rfc proposes manually disabling with a
procedure.

# Supporting Data

https://sentry.io/organizations/sentry/dashboard/7997/?project=5350637&project=4857230&project=2423079&statsPeriod=14d

# Options Considered

## manual disabling process

**a test should be disabled if it has flaked on the primary branch**

- identify the owner of the test in question
    - often `.github/CODEOWNERS` can help
    - otherwise utilize `git log -- path/to/the/test/file`
- find the corresponding sentry issue:
    - for example: [django tests](https://sentry.io/organizations/sentry/issues/?limit=5&project=2423079&query=&sort=freq&statsPeriod=14d)
- create a JIRA ticket (or if the team uses github issues, do that instead)
    - subject: `disabled flaky test: <testname>`
    - body: (something like this)

      ```
          the following test is flaky so it is being disabled:

          here is the sentry issue: <<< link here >>>

          ```
          <<< test failure output here >>>
          ```

          please fix this test and re-enable it
      ```

- make a pull request to disable the test (make sure to reference the ticket)
    - for python tests, the test can be decorated with:

      ```diff
      +@pytest.mark.skip(reason='flaky: TICKET-1234')
       def test_which_is_flaky():
      ```

    - for js tests, the test can be disabled with:

      ```diff
      -it('does the thing', () => {
      +it.skip('flaky: TICKET-1234: does the thing', () => {
      ```

## automated disabling process

this would require engineering effort to solve so for now we're choosing a
lightweight manual process

one could imagine a system where either the test runner or a test collector
knows historical data about tests and can automatically make decisions about
ignoring known failures and/or ticketing them

# Unresolved questions
