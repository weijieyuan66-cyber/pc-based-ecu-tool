"""
validation/
-----------
Dedicated expectation / validation layer.

This package owns all logic for checking whether a CAN bus session
conforms to a declared set of expectations.  It is intentionally
decoupled from:

  - the UI layer  (no tkinter imports)
  - the fault-hint rule layer  (it *produces* FaultHint objects via a
    bridge method, but does not inherit from FaultRule)
  - any specific transport backend

Public surface
--------------
  specs.py
      ExpectationSpec         -- top-level scenario descriptor
      ExpectedMessageSpec     -- per-message expectation
      ExpectedFieldConstraint -- per-byte field constraint

  results.py
      DeviationType           -- enum of known deviation categories
      DeviationEvent          -- a single detected deviation
      ValidationSummary       -- aggregated result for a session

  validator.py
      ExpectationValidator    -- stateful engine: feed frames → finalize

  mock_validation_test.py
      run_mock_validation_test()      -- standalone mock scenario runner
      mock_validation_fault_hints()   -- convenience wrapper for the UI
"""
