from agent.nodes.pricing import connects_spent_this_week, current_week


def test_connects_spent_counts_only_this_week():
    assert connects_spent_this_week({"connects_spent_week": 92, "connects_week": current_week()}) == 92
    assert connects_spent_this_week({"connects_spent_week": 92, "connects_week": "2020-W01"}) == 0
    assert connects_spent_this_week({"connects_spent_week": 92}) == 0
