"""Step platform build-step outline. Only the steps that apply are returned, in build order."""

from app.models import Part, SkeletonStep
from app.templates.step_platform import Params


def _labels(parts: list[Part], *names: str) -> list[str]:
    """Sorted unique labels of the parts with one of these names (cut-list order: A..Z, AA..)."""
    return sorted({p.label for p in parts if p.name in names}, key=lambda s: (len(s), s))


def build_skeleton_steps(params: Params, parts: list[Part]) -> list[SkeletonStep]:
    """Steps for the parts that exist. `final_check` covers every tread and riser, since the check is
    that every step is level and solid."""
    stringers = _labels(parts, "Stringer")
    treads = _labels(parts, "Tread board")
    risers = _labels(parts, "Riser")
    frame = _labels(parts, "Landing rim (side)", "Landing rim (end)", "Landing joist", "Landing post")
    deck = _labels(parts, "Landing deck board")
    steps: list[SkeletonStep] = []
    if frame:
        steps.append(SkeletonStep(phase="assemble", title="Build the top platform frame", part_labels=frame, action_key="build_platform_frame"))
    if stringers:
        steps.append(SkeletonStep(phase="cut", title="Cut the stringers", part_labels=stringers, action_key="cut_stringers"))
    if treads or risers:
        steps.append(SkeletonStep(phase="cut", title="Cut the treads and risers", part_labels=sorted(set(treads + risers), key=lambda s: (len(s), s)), action_key="cut_treads_and_risers"))
    if stringers:
        steps.append(SkeletonStep(phase="assemble", title="Set the stringers", part_labels=stringers, action_key="set_stringers"))
    if risers:
        steps.append(SkeletonStep(phase="install", title="Install the risers", part_labels=risers, action_key="install_risers"))
    if treads:
        steps.append(SkeletonStep(phase="install", title="Install the treads", part_labels=treads, action_key="install_treads"))
    if deck:
        steps.append(SkeletonStep(phase="install", title="Deck the top platform", part_labels=deck, action_key="deck_platform"))
    steps.append(SkeletonStep(phase="check", title="Check every step is level and solid", part_labels=sorted(set(treads + risers), key=lambda s: (len(s), s)), action_key="final_check"))
    return steps
