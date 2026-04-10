"""
rules/
------
Fault-hint rule layer.

Components
----------
  base_rule      -- FaultHint data class + FaultRule abstract base
  rule_engine    -- RuleEngine: applies a list of FaultRule instances to frames
  builtin_rules  -- First set of built-in fault detection rules

Usage
-----
    from rules.rule_engine import RuleEngine
    from rules.builtin_rules import create_default_rule_engine

    engine = create_default_rule_engine()
    hints = engine.evaluate(decoded_frame)
    for hint in hints:
        print(hint.severity, hint.message)
"""
