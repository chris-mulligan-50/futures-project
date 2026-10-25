from euro_roll.config import exploratory, main_test
from euro_roll.expiries import roll_calendar


def test_split_has_no_overlap_and_leaves_out_three_rolls():
    pairs = roll_calendar(2010, 2026)
    main, expl = main_test(pairs), exploratory(pairs)
    assert not set(main) & set(expl)
    assert len(main) == 57
    assert len(expl) == 8
    # Left out on purpose: 6EH0 and 6EM0 (before the dataset starts on
    # 2010-06-06) and 6EZ6 (expires 2026-12-14, after the last date).
    left_out = [p[0] for p in pairs if p not in main and p not in expl]
    assert left_out == ["6EH0", "6EM0", "6EZ6"]


def test_exploratory_rolls_are_the_eight_recent_ones():
    expl = exploratory(roll_calendar(2010, 2026))
    assert [p[0] for p in expl] == [
        "6EZ4", "6EH5", "6EM5", "6EU5", "6EZ5", "6EH6", "6EM6", "6EU6",
    ]
    assert max(p[2] for p in main_test(roll_calendar(2010, 2026))) < expl[0][2]
