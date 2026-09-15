"""
The flex layout algorithm, CSS Flexible Box Layout Module Level 1, section 9.

Pure arithmetic: no ReportLab, no canvas, no frags. The one thing it cannot
do by itself is measure an item across the other axis, which is what the
`measure_cross` callback is for. Keeping it apart from the flowable is what
lets the awkward part -- the freeze loop in 9.7, where everybody gets the
scaled shrink factor wrong -- be tested with numbers.

Positions are logical: `main_pos` runs from main-start, `cross_pos` from
cross-start, and both are the start of the item's border box, its margins
already accounted for. The reverse directions and wrap-reverse are applied
here, by mirroring, so the caller only ever maps main to x and cross to y
(or the other way round for a column).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: Comparisons against free space, which is a sum of measured floats.
_FUZZ = 1e-6


@dataclass(frozen=True)
class ItemSpec:
    """One flex item, measured along the container's axes."""

    #: flex-basis resolved to points, or None for auto / an indefinite %.
    flex_basis: float | None
    #: The main size property (width in a row), resolved, or None for auto.
    specified: float | None
    #: Main-axis content sizes: the longest word, and the longest line.
    min_content: float
    max_content: float
    grow: float = 0.0
    shrink: float = 1.0
    #: min-/max- on the main axis; None means auto / none.
    min_main: float | None = None
    max_main: float | None = None
    #: Margins along each axis; None means auto.
    margin_main_start: float | None = 0.0
    margin_main_end: float | None = 0.0
    margin_cross_start: float | None = 0.0
    margin_cross_end: float | None = 0.0
    align_self: str = "auto"
    #: The cross size property (height in a row), resolved, or None.
    cross_specified: float | None = None
    min_cross: float | None = None
    max_cross: float | None = None
    order: int = 0

    def outer(self, main: float) -> float:
        """The margin-box main size, auto margins counting as 0."""
        return main + (self.margin_main_start or 0.0) + (self.margin_main_end or 0.0)

    def outer_cross(self, cross: float) -> float:
        return cross + (self.margin_cross_start or 0.0) + (self.margin_cross_end or 0.0)


@dataclass(frozen=True)
class ContainerSpec:
    """The flex container's content box and its own properties."""

    #: None when the main size is indefinite: a column with no height.
    main_size: float | None
    cross_size: float | None
    direction: str = "row"
    wrap: str = "nowrap"
    justify_content: str = "flex-start"
    align_items: str = "stretch"
    align_content: str = "stretch"
    main_gap: float = 0.0
    cross_gap: float = 0.0

    @property
    def is_row(self) -> bool:
        return self.direction in {"row", "row-reverse"}

    @property
    def is_reversed(self) -> bool:
        return self.direction.endswith("-reverse")

    @property
    def is_single_line(self) -> bool:
        return self.wrap == "nowrap"


@dataclass
class PlacedItem:
    #: Index into the ItemSpec sequence as given, whatever `order` said.
    index: int
    line: int
    main_pos: float
    cross_pos: float
    main_size: float
    cross_size: float


@dataclass
class FlexLine:
    items: list[int]
    cross_size: float = 0.0
    cross_pos: float = 0.0


@dataclass
class FlexLayout:
    placed: list[PlacedItem] = field(default_factory=list)
    lines: list[FlexLine] = field(default_factory=list)
    #: The container's content box, once the indefinite axis is known.
    main_size: float = 0.0
    cross_size: float = 0.0


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ 9.2 Line length determination
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def _clamp(value: float, low: float | None, high: float | None) -> float:
    if high is not None:
        value = min(value, high)
    if low is not None:
        value = max(value, low)
    return value


def flex_base_size(spec: ItemSpec) -> float:
    """9.2 step 3: flex-basis, else the main size property, else content."""
    if spec.flex_basis is not None:
        return spec.flex_basis
    if spec.specified is not None:
        return spec.specified
    return spec.max_content


def automatic_minimum(spec: ItemSpec) -> float:
    """
    4.5: the automatic minimum size of a flex item, for min-main: auto.

    The content size suggestion (min-content) capped by the specified size
    and by max-main. It is what stops flex-shrink squeezing a column until
    its words break; min-width: 0 is how an author switches it off.
    """
    minimum = spec.min_content
    if spec.specified is not None:
        minimum = min(minimum, spec.specified)
    if spec.max_main is not None:
        minimum = min(minimum, spec.max_main)
    return minimum


def main_bounds(spec: ItemSpec) -> tuple[float, float | None]:
    """(min, max) used to clamp the item's main size."""
    low = spec.min_main if spec.min_main is not None else automatic_minimum(spec)
    return low, spec.max_main


def hypothetical_main_size(spec: ItemSpec) -> float:
    """9.2 step 3: the flex base size clamped by min and max."""
    low, high = main_bounds(spec)
    return _clamp(flex_base_size(spec), low, high)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ 9.3 Main size determination
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def collect_into_lines(
    specs: Sequence[ItemSpec], container: ContainerSpec, order: Sequence[int]
) -> list[list[int]]:
    """
    9.3 step 5: fill each line with as many items as fit.

    `order` is the item indices in layout order. A single-line container
    takes everything; so does one whose main size is indefinite, because
    there is nothing to wrap against. The gap counts only between items.
    """
    if container.is_single_line or container.main_size is None or not order:
        return [list(order)]

    lines: list[list[int]] = []
    current: list[int] = []
    used = 0.0
    for index in order:
        spec = specs[index]
        outer = spec.outer(hypothetical_main_size(spec))
        needed = outer if not current else used + container.main_gap + outer
        if current and needed > container.main_size + _FUZZ:
            lines.append(current)
            current, used = [index], outer
        else:
            current.append(index)
            used = needed
    lines.append(current)
    return lines


def resolve_flexible_lengths(
    line: Sequence[int], specs: Sequence[ItemSpec], available: float, gap: float
) -> list[float]:
    """
    9.7: the target main size of every item in one line.

    `available` is the container's inner main size. Returns the sizes in the
    order of `line`. Step numbers below are the specification's.
    """
    base = {i: flex_base_size(specs[i]) for i in line}
    hypothetical = {i: hypothetical_main_size(specs[i]) for i in line}
    gaps = gap * max(len(line) - 1, 0)

    # 1. Determine the used flex factor.
    outer_hypothetical = sum(specs[i].outer(hypothetical[i]) for i in line) + gaps
    growing = outer_hypothetical < available
    factor = (lambda s: s.grow) if growing else (lambda s: s.shrink)

    # 2. Size inflexible items: freeze at the hypothetical main size.
    target = dict(hypothetical)
    frozen: set[int] = set()
    for i in line:
        spec = specs[i]
        inflexible = factor(spec) == 0
        # An item already past its hypothetical size in the direction of
        # flexing has nowhere to go: its min or max got there first.
        clamped_short = growing and base[i] > hypothetical[i]
        clamped_long = not growing and base[i] < hypothetical[i]
        if inflexible or clamped_short or clamped_long:
            frozen.add(i)

    def free_space() -> float:
        # 3. Initial free space, and 4b's remaining free space: the same sum,
        # frozen items at their target size, the others at their base size.
        used = gaps
        for i in line:
            size = target[i] if i in frozen else base[i]
            used += specs[i].outer(size)
        return available - used

    initial_free = free_space()

    # 4. Loop.
    while True:
        # a. Check for flexible items.
        unfrozen = [i for i in line if i not in frozen]
        if not unfrozen:
            break

        # b. Calculate the remaining free space. When the flex factors sum to
        # less than one, the items only take that fraction of the initial
        # space; without this a lone `flex-grow: 0.5` would swallow it all.
        remaining = free_space()
        factors = sum(factor(specs[i]) for i in unfrozen)
        if factors < 1:
            scaled = initial_free * factors
            if abs(scaled) < abs(remaining):
                remaining = scaled

        # c. Distribute free space proportional to the flex factors.
        if abs(remaining) > _FUZZ:
            if growing:
                for i in unfrozen:
                    target[i] = base[i] + remaining * specs[i].grow / factors
            else:
                # The shrink factor is scaled by the base size, so a big
                # item gives up more than a small one with the same factor.
                scaled_factors = {i: specs[i].shrink * base[i] for i in unfrozen}
                total_scaled = sum(scaled_factors.values())
                for i in unfrozen:
                    share = scaled_factors[i] / total_scaled if total_scaled else 0
                    target[i] = base[i] - abs(remaining) * share
        else:
            for i in unfrozen:
                target[i] = base[i]

        # d. Fix min/max violations.
        total_violation = 0.0
        violation: dict[int, float] = {}
        for i in unfrozen:
            low, high = main_bounds(specs[i])
            clamped = _clamp(max(target[i], 0.0), low, high)
            violation[i] = clamped - target[i]
            total_violation += violation[i]
            target[i] = clamped

        # e. Freeze over-flexed items.
        if abs(total_violation) <= _FUZZ:
            frozen.update(unfrozen)
        elif total_violation > 0:
            frozen.update(i for i in unfrozen if violation[i] > 0)
        else:
            frozen.update(i for i in unfrozen if violation[i] < 0)

    return [target[i] for i in line]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ 9.4 - 9.6 Cross size and alignment
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def _align_self(spec: ItemSpec, container: ContainerSpec) -> str:
    return container.align_items if spec.align_self == "auto" else spec.align_self


def _distribute(mode: str, free: float, count: int) -> tuple[float, float]:
    """
    (leading offset, spacing between) for justify-content / align-content.

    With one item, space-between packs to the start; with no free space,
    everything packs to the start. The same rules serve both axes.
    """
    if count == 0:
        return 0.0, 0.0
    if free < 0 and mode in {"space-between", "space-around", "space-evenly"}:
        return 0.0, 0.0
    if mode == "flex-end":
        return free, 0.0
    if mode == "center":
        return free / 2.0, 0.0
    if mode == "space-between":
        return (0.0, free / (count - 1)) if count > 1 else (0.0, 0.0)
    if mode == "space-around":
        each = free / count
        return each / 2.0, each
    if mode == "space-evenly":
        each = free / (count + 1)
        return each, each
    return 0.0, 0.0


def resolve_flex_layout(
    specs: Sequence[ItemSpec],
    container: ContainerSpec,
    measure_cross: Callable[[int, float], float],
) -> FlexLayout:
    """
    Lay the items out; the whole of section 9, in order.

    `measure_cross(index, main_size)` is the item's content cross size once
    its main size is known: in a row, the height its content takes at that
    width. It is the only thing that needs the outside world.
    """
    layout = FlexLayout()
    if not specs:
        layout.main_size = container.main_size or 0.0
        layout.cross_size = container.cross_size or 0.0
        return layout

    # 5.4.1: order changes what the layout sees, not the sequence returned.
    order = sorted(range(len(specs)), key=lambda i: (specs[i].order, i))

    lines = collect_into_lines(specs, container, order)

    # 9.3 step 4: an indefinite main size (a column without a height) is the
    # content's own: nothing grows, nothing shrinks, one line.
    if container.main_size is None:
        main_size = max(
            sum(specs[i].outer(hypothetical_main_size(specs[i])) for i in line)
            + container.main_gap * (len(line) - 1)
            for line in lines
        )
    else:
        main_size = container.main_size
    layout.main_size = main_size

    # 9.3 step 6 and 9.4 step 7: main sizes, then cross sizes at those.
    main: dict[int, float] = {}
    cross_hypothetical: dict[int, float] = {}
    for line in lines:
        sizes = resolve_flexible_lengths(line, specs, main_size, container.main_gap)
        for i, size in zip(line, sizes, strict=True):
            main[i] = size
            spec = specs[i]
            cross = (
                spec.cross_specified
                if spec.cross_specified is not None
                else measure_cross(i, size)
            )
            cross_hypothetical[i] = _clamp(cross, spec.min_cross, spec.max_cross)

    # 9.4 step 8: the cross size of each line.
    flex_lines = [FlexLine(items=line) for line in lines]
    if len(flex_lines) == 1 and container.cross_size is not None:
        flex_lines[0].cross_size = container.cross_size
    else:
        for flex_line in flex_lines:
            flex_line.cross_size = max(
                specs[i].outer_cross(cross_hypothetical[i]) for i in flex_line.items
            )

    # 9.4 step 15 and 9.6 step 16: the container's cross size, and how the
    # lines share it. align-content acts only on a definite cross size.
    lines_cross = sum(fl.cross_size for fl in flex_lines) + container.cross_gap * (
        len(flex_lines) - 1
    )
    if container.cross_size is None:
        cross_size = lines_cross
        leading, between = 0.0, 0.0
    else:
        cross_size = container.cross_size
        free = cross_size - lines_cross
        if container.align_content == "stretch" and free > 0:
            for flex_line in flex_lines:
                flex_line.cross_size += free / len(flex_lines)
            leading, between = 0.0, 0.0
        else:
            leading, between = _distribute(
                container.align_content, free, len(flex_lines)
            )
    layout.cross_size = cross_size

    position = leading
    for flex_line in flex_lines:
        flex_line.cross_pos = position
        position += flex_line.cross_size + container.cross_gap + between

    # 9.4 step 11: used cross size; stretch fills the line.
    for flex_line in flex_lines:
        for i in flex_line.items:
            spec = specs[i]
            if (
                _align_self(spec, container) == "stretch"
                and spec.cross_specified is None
                and spec.margin_cross_start is not None
                and spec.margin_cross_end is not None
            ):
                stretched = flex_line.cross_size - spec.outer_cross(0.0)
                cross_hypothetical[i] = _clamp(
                    stretched, spec.min_cross, spec.max_cross
                )

    # 9.5 step 12: main-axis alignment, auto margins first.
    # 9.6 steps 13-14: cross-axis alignment, auto margins first.
    for line_number, flex_line in enumerate(flex_lines):
        items = flex_line.items
        used = sum(specs[i].outer(main[i]) for i in items) + container.main_gap * (
            len(items) - 1
        )
        free = main_size - used
        auto_margins = sum(
            (specs[i].margin_main_start is None) + (specs[i].margin_main_end is None)
            for i in items
        )
        if auto_margins and free > 0:
            auto_share = free / auto_margins
            leading, between = 0.0, 0.0
        else:
            auto_share = 0.0
            leading, between = _distribute(container.justify_content, free, len(items))

        cursor = leading
        for i in items:
            spec = specs[i]
            start = spec.margin_main_start
            end = spec.margin_main_end
            cursor += auto_share if start is None else start
            main_pos = cursor
            cursor += main[i] + (auto_share if end is None else end)
            cursor += container.main_gap + between

            cross = cross_hypothetical[i]
            cross_free = flex_line.cross_size - spec.outer_cross(cross)
            cross_start = spec.margin_cross_start
            cross_end = spec.margin_cross_end
            if cross_start is None or cross_end is None:
                if cross_start is None and cross_end is None:
                    offset = max(cross_free, 0.0) / 2.0
                elif cross_start is None:
                    offset = max(cross_free, 0.0)
                else:
                    offset = 0.0
                offset += cross_start or 0.0
            else:
                mode = _align_self(spec, container)
                if mode == "flex-end":
                    offset = cross_free
                elif mode == "center":
                    offset = cross_free / 2.0
                else:
                    offset = 0.0
                offset += cross_start

            layout.placed.append(
                PlacedItem(
                    index=i,
                    line=line_number,
                    main_pos=main_pos,
                    cross_pos=flex_line.cross_pos + offset,
                    main_size=main[i],
                    cross_size=cross,
                )
            )

    # The reverse directions swap main-start and main-end; wrap-reverse
    # swaps cross-start and cross-end. Mirroring the finished positions is
    # exactly that swap, and it carries justify-content, the auto margins and
    # align-self along with it.
    if container.is_reversed:
        for item in layout.placed:
            item.main_pos = main_size - item.main_pos - item.main_size
    if container.wrap == "wrap-reverse":
        for item in layout.placed:
            item.cross_pos = cross_size - item.cross_pos - item.cross_size
        for flex_line in flex_lines:
            flex_line.cross_pos = (
                cross_size - flex_line.cross_pos - flex_line.cross_size
            )

    layout.placed.sort(key=lambda item: item.index)
    layout.lines = flex_lines
    return layout
