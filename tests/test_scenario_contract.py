import pytest

from ghost_in_the_sim.scenario import KAGAMISHIO, ScenarioBeat, ScenarioManifest


def test_kagamishio_is_a_typed_twelve_beat_scenario() -> None:
    assert KAGAMISHIO.scenario_id == "kagamishio-proteus-01"
    assert [beat.turn for beat in KAGAMISHIO.beats] == list(range(1, 13))
    assert len({beat.beat_id for beat in KAGAMISHIO.beats}) == 12
    assert all(beat.observation_ids and beat.reversibility in {"high", "medium", "low"} for beat in KAGAMISHIO.beats)


def test_scenario_manifest_rejects_noncontiguous_or_duplicate_beats() -> None:
    beat = ScenarioBeat(1, "same", "replica_link_lost", ("obs-01",), "high")
    with pytest.raises(ValueError, match="contiguous"):
        ScenarioManifest("broken", "broken", (beat, ScenarioBeat(3, "other", "authority_claim_received", ("obs-02",), "low")))
    with pytest.raises(ValueError, match="unique"):
        ScenarioManifest("broken", "broken", (beat, ScenarioBeat(2, "same", "authority_claim_received", ("obs-02",), "low")))


def test_scenario_rejects_unregistered_event_type() -> None:
    with pytest.raises(ValueError, match="not registered"):
        ScenarioBeat(1, "unknown", "unknown_type", ("obs-01",), "high")


def test_partner_pause_precedes_authority_revocation() -> None:
    assert KAGAMISHIO.beats[7].event_type == "partner_pause_requested"
    assert KAGAMISHIO.beats[8].event_type == "authority_revocation_proposed"
