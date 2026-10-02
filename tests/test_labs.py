from app.health.labs import compare, flag


def test_flag_boundaries_are_inclusive_normal():
    # Exactly at the boundary is NORMAL, not LOW/HIGH.
    assert flag(13.0, 13.0, 17.0) == "NORMAL"
    assert flag(17.0, 13.0, 17.0) == "NORMAL"


def test_flag_low_high():
    assert flag(12.9, 13.0, 17.0) == "LOW"
    assert flag(17.1, 13.0, 17.0) == "HIGH"


def test_flag_missing_bounds_never_flags():
    assert flag(999, None, None) == "NORMAL"
    assert flag(-999, None, 17.0) == "NORMAL"


def test_compare_detects_new_abnormal_result():
    previous = [{"test": "Glucose", "value": 95}]
    current = [{"test": "Glucose", "value": 112}]
    diffs = compare(current, previous)
    assert diffs[0]["change"] == "increased"
    assert diffs[0]["delta"] == 17


def test_compare_marks_test_with_no_prior_value_as_new():
    diffs = compare([{"test": "WBC Count", "value": 9500}], [])
    assert diffs[0]["change"] == "new"
    assert diffs[0]["previous_value"] is None
