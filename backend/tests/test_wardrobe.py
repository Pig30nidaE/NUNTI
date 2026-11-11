from types import SimpleNamespace
import pytest
from nunti.avatar_studio.wardrobe import WardrobeInput, brief, create, budget, CAP_MICROS
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
    assert first["design"]["wardrobe"]["look"] == "formal"
    assert budget(store)["reservedUsd"] == 2


def test_budget_refuses_before_provider_and_failure_keeps_reservation(tmp_path):
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")
    def failed(*args):
        raise StudioError("WARDROBE_RESULT_UNKNOWN")
    value = WardrobeInput(destination={"name":"서울"}, purpose="면접")
    with pytest.raises(StudioError):
        create(settings, store, "owner", value, failed)
    assert budget(store)["reservedUsd"] == 2
    with store.connect() as db:
        db.execute("UPDATE requests SET reserved_micros=?", (CAP_MICROS,))
    with pytest.raises(StudioError, match="IMAGE_API_BUDGET_REACHED"):
        create(settings, store, "owner", WardrobeInput(destination={"name":"병원"}), lambda *a: pytest.fail("must not spend"))


@pytest.mark.parametrize("purpose,look", [("면접","formal"),("병원 진료","medical"),("축구 경기 관람","football")])
def test_context_and_explicit_mood_affect_versioned_brief(purpose, look):
    value = WardrobeInput(destination={"name":"서울"}, purpose=purpose, mood="calm")
    _, seed, result = brief(value)
    assert result["id"] == look
    assert seed != brief(value.model_copy(update={"mood":"curious"}))[1]


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
