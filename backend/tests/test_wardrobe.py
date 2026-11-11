from types import SimpleNamespace
import pytest
from nunti.avatar_studio.models import digest
from nunti.avatar_studio.wardrobe import (
    CAP_MICROS, LEGACY_VERSION, REFERENCE, RESERVE_MICROS, WardrobeInput, brief, budget, build_prompt, create, wardrobe_claim,
)
from nunti.avatar_studio.storage import StudioStore, StudioError


def test_same_brief_is_cached_without_second_paid_call(tmp_path):
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")
    calls = []
    def render(key, prompt):
        calls.append(prompt)
        return b"fake-png", {}, 100_000
    value = WardrobeInput(destination={"name":"서울"}, purpose="면접", mood="calm")
    first = create(settings, store, "owner", value, render)
    second = create(settings, store, "owner", value, render)
    assert first == second and len(calls) == 1
    assert first["design"]["wardrobe"]["look"] == "personal"
    assert budget(store)["reservedUsd"] == RESERVE_MICROS / 1_000_000


def test_budget_refuses_before_provider_and_failure_keeps_reservation(tmp_path):
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")
    def failed(*args):
        raise StudioError("WARDROBE_RESULT_UNKNOWN")
    value = WardrobeInput(destination={"name":"서울"}, purpose="면접")
    with pytest.raises(StudioError):
        create(settings, store, "owner", value, failed)
    assert budget(store)["reservedUsd"] == RESERVE_MICROS / 1_000_000
    with store.connect() as db:
        db.execute("UPDATE requests SET reserved_micros=?", (CAP_MICROS,))
    with pytest.raises(StudioError, match="IMAGE_API_BUDGET_REACHED"):
        create(settings, store, "owner", WardrobeInput(destination={"name":"병원"}, purpose="외래 진료"), lambda *a: pytest.fail("must not spend"))


def test_undecided_destination_keeps_base_character_without_paid_call(tmp_path):
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")
    value = WardrobeInput(destination={"name":"아직 미정"})
    artifact = create(settings, store, "owner", value, lambda *a: pytest.fail("must not call image provider"))
    assert artifact["design"]["wardrobe"]["look"] == "default"
    assert artifact["displayName"] == "기본 눈티"
    assert budget(store)["calls"] == 0


@pytest.mark.parametrize("purpose", [
    "도자기 공방에서 첫 접시를 빚으러", "친구의 독립영화 첫 상영을 보러",
    "병원 진료가 아니라 로비에서 열리는 작은 사진 전시를 보러",
])
def test_freeform_context_and_explicit_mood_affect_versioned_brief(purpose):
    value = WardrobeInput(destination={"name":"서울"}, purpose=purpose, mood="calm")
    _, seed, result = brief(value)
    assert result["id"] == "personal"
    assert purpose in build_prompt(value, seed, result)
    assert seed != brief(value.model_copy(update={"mood":"curious"}))[1]


def test_legacy_purchase_reuses_original_character(tmp_path):
    store = StudioStore(tmp_path)
    value = WardrobeInput(destination={"name": "서울"}, purpose="면접")
    raw = value.model_dump(exclude_none=True)
    claim = wardrobe_claim(raw, LEGACY_VERSION, digest(REFERENCE.read_bytes()))
    store.claim("owner", claim, reserved=2_000_000, cap=CAP_MICROS)
    character = {"characterId": "nunti-" + claim["requestId"], "design": {"wardrobe": {"look": "formal"}}}
    store.complete("owner", claim["requestId"], character)
    assert create(SimpleNamespace(wardrobe_available=True), store, "owner", value,
                  lambda *_: pytest.fail("must reuse a purchased wardrobe")) == character
    assert budget(store)["calls"] == 1


def test_changed_api_route_is_rejected_before_paid_reservation(tmp_path):
    from nunti.avatar_studio.models import canonical, digest
    from nunti.avatar_studio.route_api import PlanStore
    store = StudioStore(tmp_path)
    plan = {"destination":{"name":"회사"},"routePoints":[[0.1,0.2],[0.8,0.9]]}
    plan["planId"] = digest(canonical(plan).encode())
    PlanStore(store).put("owner",plan)
    route = {"confirmed":True,"inputOrigin":"API_ROUTE","sourceLabel":"시험 경로",
             "apiPlanId":plan["planId"],"points":[[0.1,0.1],[0.9,0.9]]}
    value = WardrobeInput(destination={"name":plan["destination"]["name"]}, purpose="면접", route=route)
    with pytest.raises(StudioError, match="API_ROUTE_POINTS_MISMATCH"):
        create(SimpleNamespace(wardrobe_available=True,image_key="test"),store,"owner",value,
               lambda *args: pytest.fail("Changed route must not call a paid model"))
    assert budget(store)["reservedUsd"] == 0
