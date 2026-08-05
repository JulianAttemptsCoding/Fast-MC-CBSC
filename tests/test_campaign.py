"""Contracts for the unattended campaign decision logic.

These run without a GPU, a pod, or a network. The point is that the rules an
operator would otherwise have to remember -- absolute epoch targets, patience
equal to the horizon, and what a structural invariant failure means for a
family -- are executable rather than documentary.
"""

from __future__ import annotations

import pytest

from cbsc_zdc.training.campaign import (
    ALLOWED_CONFIG_DELTA,
    CampaignError,
    SegmentResult,
    absolute_epoch_target,
    classify,
    config_delta,
    family_is_still_improving,
    verify_config_delta,
)


def _rows(pairs):
    return [{"epoch": e, "validation_loss": v} for e, v in pairs]


# --------------------------------------------------------------------------
# absolute epoch arithmetic
# --------------------------------------------------------------------------


def test_epochs_is_an_absolute_target_not_a_count_of_new_epochs():
    """The misread that cost the whole dicos-r1 wave, pinned.

    lr3e4's accepted parent ends at epoch 22, so 20 further epochs is 43, not
    20. Setting it to 20 does not error -- it silently runs no epochs, or with a
    restarted scheduler anneals to the minimum learning rate across too few.
    """
    assert absolute_epoch_target(22, 20) == 43
    assert absolute_epoch_target(38, 24) == 63  # the real dicos-p10 arithmetic
    assert absolute_epoch_target(4, 6) == 11
    assert absolute_epoch_target(0, 1) == 2


def test_a_segment_must_request_at_least_one_epoch():
    with pytest.raises(CampaignError, match="at least one further epoch"):
        absolute_epoch_target(22, 0)
    with pytest.raises(CampaignError):
        absolute_epoch_target(22, -5)


def test_parent_last_epoch_must_be_nonnegative():
    with pytest.raises(CampaignError, match="nonnegative"):
        absolute_epoch_target(-1, 20)


# --------------------------------------------------------------------------
# the owner's continue rule
# --------------------------------------------------------------------------


def test_best_within_the_window_of_the_latest_epoch_continues_the_family():
    still_moving = SegmentResult(
        exit_code=0, epochs=_rows([(23, 4.60), (24, 4.58), (40, 4.55), (43, 4.56)])
    )
    assert family_is_still_improving(still_moving, window=6) is True
    outcome, reason = classify(still_moving, window=6, has_next_family=True)
    assert outcome == "continue_same_family"
    assert "still improving" in reason
    assert "40" in reason and "43" in reason


def test_best_outside_the_window_advances_to_the_next_family():
    plateaued = SegmentResult(
        exit_code=0, epochs=_rows([(23, 4.55), (30, 4.56), (43, 4.57)])
    )
    assert family_is_still_improving(plateaued, window=6) is False
    outcome, reason = classify(plateaued, window=6, has_next_family=True)
    assert outcome == "advance_family"
    assert "plateaued" in reason


def test_the_window_boundary_is_inclusive():
    """Exactly `window` epochs behind still counts as improving."""
    exactly_six = SegmentResult(exit_code=0, epochs=_rows([(37, 4.50), (43, 4.51)]))
    assert family_is_still_improving(exactly_six, window=6) is True

    seven = SegmentResult(exit_code=0, epochs=_rows([(36, 4.50), (43, 4.51)]))
    assert family_is_still_improving(seven, window=6) is False


def test_a_plateau_with_no_family_left_completes_the_campaign():
    plateaued = SegmentResult(exit_code=0, epochs=_rows([(23, 4.55), (43, 4.57)]))
    outcome, reason = classify(plateaued, window=6, has_next_family=False)
    assert outcome == "campaign_complete"
    assert "no family remains" in reason


def test_ties_on_loss_resolve_to_the_earlier_epoch():
    """Checkpoint selection keeps the first epoch to reach the best value.

    Resolving a tie forward would make a family look like it is still improving
    when it has been flat for the whole segment.
    """
    flat = SegmentResult(exit_code=0, epochs=_rows([(30, 4.5), (43, 4.5)]))
    assert flat.best() == (30, 4.5)
    assert family_is_still_improving(flat, window=6) is False


# --------------------------------------------------------------------------
# what a structural invariant failure means
# --------------------------------------------------------------------------


def test_an_invariant_failure_is_terminal_for_its_family():
    """It cannot be resumed, in either direction.

    The failing last.pt is quarantined by AGENTS.md. Resuming from the segment's
    best re-runs the identical epochs under restored RNG against a fixed 50x5
    visual bank, so it reproduces the same failure forever.
    """
    died = SegmentResult(
        exit_code=1, epochs=_rows([(39, 4.66), (40, 4.70)]), invariant_failure=True
    )
    outcome, reason = classify(died, has_next_family=True)
    assert outcome == "advance_family"
    assert "quarantined" in reason
    assert "deterministically reproduce" in reason


def test_an_invariant_failure_with_no_family_left_halts_rather_than_looping():
    died = SegmentResult(exit_code=1, epochs=_rows([(40, 4.70)]), invariant_failure=True)
    outcome, _ = classify(died, has_next_family=False)
    assert outcome == "halted"


def test_a_nonzero_exit_without_an_invariant_failure_is_resumable():
    """Pod expiry, OOM and an operator stop are external, not evidence."""
    killed = SegmentResult(exit_code=137, epochs=_rows([(23, 4.60), (31, 4.57)]))
    outcome, reason = classify(killed, has_next_family=True)
    assert outcome == "resume_same_segment"
    assert "31" in reason
    assert "resumable" in reason


def test_a_crash_before_any_epoch_halts_because_there_is_nothing_to_resume_from():
    stillborn = SegmentResult(exit_code=1, epochs=[])
    outcome, reason = classify(stillborn, has_next_family=True)
    assert outcome == "halted"
    assert "no verified checkpoint" in reason


def test_a_clean_exit_with_no_epochs_halts_rather_than_advancing_silently():
    empty = SegmentResult(exit_code=0, epochs=[])
    outcome, reason = classify(empty, has_next_family=True)
    assert outcome == "halted"
    assert "recorded no epoch" in reason


def test_last_epoch_written_overrides_the_history_maximum():
    """A row can be appended for an epoch whose checkpoint never landed."""
    result = SegmentResult(
        exit_code=137, epochs=_rows([(30, 4.6), (31, 4.5)]), last_epoch_written=30
    )
    assert result.latest_epoch == 30


# --------------------------------------------------------------------------
# the config guard, which is what makes unattended freezing safe
# --------------------------------------------------------------------------


def _parent_config():
    return {
        "project": {"name": "cbsc-lr3e4", "run_dir": "runs/a"},
        "training": {
            "epochs": 23,
            "learning_rate": 3e-4,
            "batch_size": 6,
            "seed": 20260724,
            "early_stopping_patience": 6,
            "resume_from_sha256": "a" * 64,
        },
        "evaluation": {"closure_tolerance_gev": 2e-5, "profile_steps": 8},
        "loss_weights": {"visible": 2.574416711989658},
    }


def test_an_ordinary_continuation_delta_is_accepted():
    parent = _parent_config()
    child = _parent_config()
    child["project"]["name"] = "cbsc-lr3e4-dicos-c1"
    child["project"]["run_dir"] = "runs/b"
    child["training"]["epochs"] = 43
    child["training"]["early_stopping_patience"] = 20
    child["training"]["resume_from_sha256"] = "b" * 64
    child["evaluation"]["closure_tolerance_relative"] = 1e-5
    child["provenance"] = {"parent_last_epoch": 22}

    delta = verify_config_delta(parent, child)
    assert "training.epochs" in delta
    assert delta["training.epochs"] == (23, 43)
    assert "evaluation.closure_tolerance_relative" in delta


@pytest.mark.parametrize(
    "path,value",
    [
        (("training", "learning_rate"), 1e-4),
        (("training", "batch_size"), 12),
        (("training", "seed"), 1),
        (("evaluation", "profile_steps"), 16),
        (("evaluation", "closure_tolerance_gev"), 1e-3),
        (("loss_weights", "visible"), 1.0),
    ],
)
def test_a_moved_invariant_is_refused(path, value):
    """Every one of these is listed as invariant across a backend move.

    An unattended process freezes configs with nobody reading the diff, so the
    diff must be read by the process. A silently changed learning rate would
    make the whole campaign incomparable to everything before it.
    """
    parent = _parent_config()
    child = _parent_config()
    section, key = path
    child[section][key] = value
    with pytest.raises(CampaignError, match="outside the allowed continuation"):
        verify_config_delta(parent, child)


def test_the_refusal_names_the_field_and_both_values():
    parent = _parent_config()
    child = _parent_config()
    child["training"]["learning_rate"] = 1e-4
    with pytest.raises(CampaignError) as excinfo:
        verify_config_delta(parent, child)
    message = str(excinfo.value)
    assert "training.learning_rate" in message
    assert "0.0003" in message and "0.0001" in message


def test_provenance_is_exempt_because_recording_the_change_is_its_job():
    parent = _parent_config()
    child = _parent_config()
    child["provenance"] = {"anything": "at all", "nested": {"also": "fine"}}
    verify_config_delta(parent, child)


def test_an_added_or_removed_key_is_reported_rather_than_ignored():
    parent = _parent_config()
    child = _parent_config()
    child["training"]["surprise_flag"] = True
    delta = config_delta(parent, child)
    assert delta["training.surprise_flag"] == ("<absent>", True)
    with pytest.raises(CampaignError):
        verify_config_delta(parent, child)


def test_the_allowlist_does_not_contain_a_scientific_value():
    """A guard is only as good as its allowlist; this pins what may be in it."""
    forbidden = {
        "training.learning_rate",
        "training.batch_size",
        "training.seed",
        "training.gradient_accumulation",
        "training.num_workers",
        "evaluation.closure_tolerance_gev",
        "evaluation.profile_steps",
        "evaluation.share_steps",
    }
    assert not (forbidden & ALLOWED_CONFIG_DELTA)
