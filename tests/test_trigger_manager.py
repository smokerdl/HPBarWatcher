from app.automation.trigger_manager import ThresholdTrigger


def test_only_downward_crossing_fires_and_rearms_on_recovery():
    trigger = ThresholdTrigger()
    assert not trigger.update(100, 30, detected=True)
    assert not trigger.update(31, 30, detected=True)
    assert trigger.update(29, 30, detected=True)
    assert not trigger.update(15, 30, detected=True)
    assert not trigger.update(35, 30, detected=True)
    assert trigger.update(28, 30, detected=True)


def test_starting_below_threshold_does_not_fire():
    trigger = ThresholdTrigger()
    assert not trigger.update(10, 30, detected=True)
    assert not trigger.update(5, 30, detected=True)
    assert not trigger.update(30, 30, detected=True)
    assert trigger.update(29, 30, detected=True)


def test_missing_bar_disarms_and_prevents_false_reappearance_trigger():
    trigger = ThresholdTrigger()
    assert not trigger.update(100, 30, detected=True)
    assert not trigger.update(10, 30, detected=False)
    assert not trigger.update(5, 30, detected=True)
    assert not trigger.update(45, 30, detected=True)
    assert trigger.update(29, 30, detected=True)


def test_disabled_resource_requires_recovery_before_triggering():
    trigger = ThresholdTrigger()
    assert not trigger.update(100, 30, detected=True, enabled=False)
    assert not trigger.update(10, 30, detected=True, enabled=True)
    assert not trigger.update(40, 30, detected=True, enabled=True)
    assert trigger.update(20, 30, detected=True, enabled=True)
