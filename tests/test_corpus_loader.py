from mris.corpus import RULES_DIR, load_rules, rule_file


def test_load_rules_excludes_template_and_loads_executable_rules():
    rules = load_rules()

    assert rules
    assert "TEMPLATE-ENTERPRISE-RULE" not in rules

    for rule_id in rules:
        path = rule_file(rule_id)
        assert path.is_file()
        assert path.parent == RULES_DIR or RULES_DIR in path.parents


def test_rule_file_resolves_nested_rules():
    rules = load_rules()

    for rule_id in rules:
        path = rule_file(rule_id)
        assert path.name == f"{rule_id}.yaml"
