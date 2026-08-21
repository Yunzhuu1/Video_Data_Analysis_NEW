from app.prompts.semantic import SEMANTIC_SYSTEM_PROMPT, build_semantic_user_prompt


def test_prompt_teaches_metric_value_filter_contract():
    assert "超过/高于/大于/不低于/低于" in SEMANTIC_SYSTEM_PROMPT
    assert "completion_rate" in SEMANTIC_SYSTEM_PROMPT
    assert "op:>" in SEMANTIC_SYSTEM_PROMPT
    assert "HAVING" in SEMANTIC_SYSTEM_PROMPT


def test_prompt_keeps_metric_and_dimension_filters_distinct():
    catalog = [{
        "metricCode": "completion_rate",
        "metricName": "完播率",
        "businessDefinition": "平均完播率",
        "dimensions": ["category", "creator"],
    }]
    prompt = build_semantic_user_prompt("完播率超过50%的创作者", catalog, [])
    assert "completion_rate" in prompt
    assert "完播率超过50%的创作者" in prompt


def test_native_metric_dimensions_do_not_drop_explicit_creator():
    catalog = [{
        "metricCode": "completion_rate", "metricName": "完播率",
        "businessDefinition": "平均完播率", "dimensions": ["content"],
    }]
    prompt = build_semantic_user_prompt(
        "每位创作者的完播率", catalog,
        [{"code": "creator", "name": "创作者", "description": "creator_id"}],
    )
    assert "原生能力提示，不是抽取白名单" in SEMANTIC_SYSTEM_PROMPT
    assert "每位创作者的完播率" in prompt
    assert "creator" in prompt
