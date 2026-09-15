"""
The flex algorithm on numbers alone, with no PDF behind it.

Each test is a small container and the positions the specification gives
for it. measure_cross is a lambda: it stands in for the height a flowable
would take at a given width.
"""

from typing import Any
from unittest import TestCase

from xhtml2pdf.builders.flex_layout import (
    ContainerSpec,
    ItemSpec,
    collect_into_lines,
    flex_base_size,
    resolve_flex_layout,
    resolve_flexible_lengths,
)


def item(**kwargs) -> ItemSpec:
    defaults: dict[str, Any] = {
        "flex_basis": None,
        "specified": None,
        "min_content": 10.0,
        "max_content": 50.0,
    }
    defaults.update(kwargs)
    return ItemSpec(**defaults)


def container(main=300.0, cross=None, **kwargs) -> ContainerSpec:
    return ContainerSpec(main_size=main, cross_size=cross, **kwargs)


def layout(specs, spec=None, measure=None):
    return resolve_flex_layout(
        specs, spec or container(), measure or (lambda _i, _main: 20.0)
    )


def sizes(specs, spec=None, measure=None) -> list[float]:
    return [round(p.main_size, 3) for p in layout(specs, spec, measure).placed]


def positions(specs, spec=None, measure=None) -> list[float]:
    return [round(p.main_pos, 3) for p in layout(specs, spec, measure).placed]


class FlexBaseSizeTest(TestCase):
    def test_flex_basis_wins_over_the_size_property(self) -> None:
        self.assertEqual(30, flex_base_size(item(flex_basis=30, specified=80)))

    def test_the_size_property_wins_over_content(self) -> None:
        self.assertEqual(80, flex_base_size(item(specified=80)))

    def test_content_is_the_last_resort(self) -> None:
        self.assertEqual(50, flex_base_size(item()))


class ResolveFlexibleLengthsTest(TestCase):
    """9.7, item by item."""

    def test_single_line_without_flexibility_keeps_base_sizes(self) -> None:
        specs = [item(specified=50), item(specified=80)]
        self.assertEqual([50, 80], sizes(specs))
        self.assertEqual([0, 50], positions(specs))

    def test_grow_distributes_free_space_in_proportion(self) -> None:
        specs = [item(flex_basis=0, grow=g) for g in (1, 2, 1)]
        self.assertEqual([100, 200, 100], sizes(specs, container(400)))

    def test_grow_respects_max_width_and_redistributes_to_the_others(self) -> None:
        specs = [item(flex_basis=0, grow=1, max_main=50), item(flex_basis=0, grow=1)]
        self.assertEqual([50, 250], sizes(specs))

    def test_a_flex_factor_below_one_takes_only_that_fraction(self) -> None:
        specs = [item(flex_basis=0, grow=0.5)]
        self.assertEqual([100], sizes(specs, container(200)))

    def test_shrink_is_weighted_by_base_size(self) -> None:
        # 60pt over: the 200pt item gives up two thirds of it.
        specs = [item(specified=200, min_main=0), item(specified=100, min_main=0)]
        self.assertEqual([160, 80], sizes(specs, container(240)))

    def test_shrink_stops_at_the_automatic_minimum_size(self) -> None:
        # The first would go to 133; its longest word is 150, so it stops
        # there and the second takes the rest of the squeeze.
        specs = [
            item(specified=200, min_content=150),
            item(specified=100, min_content=0),
        ]
        self.assertEqual([150, 50], sizes(specs, container(200)))

    def test_min_width_zero_disables_the_automatic_minimum(self) -> None:
        specs = [
            item(specified=200, min_content=150, min_main=0),
            item(specified=100, min_content=0, min_main=0),
        ]
        self.assertEqual([133.333, 66.667], sizes(specs, container(200)))

    def test_flex_basis_zero_ignores_content_size(self) -> None:
        specs = [item(flex_basis=0, grow=1, max_content=500, min_content=0)]
        self.assertEqual([300], sizes(specs))

    def test_negative_free_space_with_zero_shrink_overflows(self) -> None:
        specs = [item(specified=200, shrink=0), item(specified=200, shrink=0)]
        self.assertEqual([200, 200], sizes(specs))
        self.assertEqual([0, 200], positions(specs))

    def test_the_gap_is_not_flexible_space(self) -> None:
        specs = [item(flex_basis=0, grow=1), item(flex_basis=0, grow=1)]
        self.assertEqual([140, 140], sizes(specs, container(300, main_gap=20)))
        self.assertEqual([0, 160], positions(specs, container(300, main_gap=20)))

    def test_direct_call_returns_sizes_in_line_order(self) -> None:
        specs = [item(flex_basis=0, grow=1), item(flex_basis=0, grow=3)]
        self.assertEqual([25, 75], resolve_flexible_lengths([0, 1], specs, 100, 0))
        self.assertEqual([75, 25], resolve_flexible_lengths([1, 0], specs, 100, 0))


class LineCollectionTest(TestCase):
    """9.3 step 5."""

    def test_nowrap_never_breaks_lines(self) -> None:
        specs = [item(specified=200, min_main=0) for _ in range(3)]
        result = layout(specs)
        self.assertEqual(1, len(result.lines))
        self.assertEqual([100, 100, 100], sizes(specs))

    def test_wrap_fills_lines_greedily(self) -> None:
        specs = [item(specified=120) for _ in range(3)]
        lines = collect_into_lines(specs, container(300, wrap="wrap"), [0, 1, 2])
        self.assertEqual([[0, 1], [2]], lines)

    def test_gaps_count_only_between_items(self) -> None:
        specs = [item(specified=120) for _ in range(3)]
        fits = collect_into_lines(
            specs, container(300, wrap="wrap", main_gap=30), [0, 1, 2]
        )
        self.assertEqual([[0, 1], [2]], fits)
        too_wide = collect_into_lines(
            specs, container(300, wrap="wrap", main_gap=70), [0, 1, 2]
        )
        self.assertEqual([[0], [1], [2]], too_wide)

    def test_an_item_wider_than_the_line_gets_a_line_of_its_own(self) -> None:
        specs = [item(specified=400, shrink=0), item(specified=50)]
        lines = collect_into_lines(specs, container(300, wrap="wrap"), [0, 1])
        self.assertEqual([[0], [1]], lines)

    def test_lines_stack_along_the_cross_axis(self) -> None:
        specs = [item(specified=200) for _ in range(2)]
        result = layout(specs, container(300, wrap="wrap", cross_gap=5))
        self.assertEqual([0, 25], [p.cross_pos for p in result.placed])
        self.assertEqual(45, result.cross_size)

    def test_wrap_reverse_reverses_line_order(self) -> None:
        specs = [item(specified=200) for _ in range(2)]
        result = layout(specs, container(300, wrap="wrap-reverse"))
        self.assertEqual([20, 0], [p.cross_pos for p in result.placed])


class MainAxisAlignmentTest(TestCase):
    """9.5, justify-content and the auto margins."""

    def setUp(self) -> None:
        self.specs = [item(specified=50) for _ in range(3)]

    def test_space_between_puts_no_space_at_the_edges(self) -> None:
        spec = container(justify_content="space-between")
        self.assertEqual([0, 125, 250], positions(self.specs, spec))

    def test_space_around_halves_the_edge_gaps(self) -> None:
        spec = container(justify_content="space-around")
        self.assertEqual([25, 125, 225], positions(self.specs, spec))

    def test_space_evenly_equalises_them(self) -> None:
        spec = container(justify_content="space-evenly")
        self.assertEqual([37.5, 125, 212.5], positions(self.specs, spec))

    def test_center_and_flex_end(self) -> None:
        self.assertEqual(
            [75, 125, 175], positions(self.specs, container(justify_content="center"))
        )
        self.assertEqual(
            [150, 200, 250],
            positions(self.specs, container(justify_content="flex-end")),
        )

    def test_space_between_with_one_item_is_flex_start(self) -> None:
        spec = container(justify_content="space-between")
        self.assertEqual([0], positions([item(specified=50)], spec))

    def test_overflowing_content_packs_to_the_start(self) -> None:
        specs = [item(specified=200, shrink=0), item(specified=200, shrink=0)]
        spec = container(justify_content="space-around")
        self.assertEqual([0, 200], positions(specs, spec))

    def test_auto_main_margin_absorbs_free_space_and_overrides_justify(self) -> None:
        specs = [item(specified=50, margin_main_end=None), item(specified=50)]
        spec = container(justify_content="center")
        self.assertEqual([0, 250], positions(specs, spec))

    def test_two_auto_margins_share_the_space(self) -> None:
        specs = [item(specified=50, margin_main_start=None, margin_main_end=None)]
        self.assertEqual([125], positions(specs))

    def test_a_fixed_margin_is_part_of_the_outer_size(self) -> None:
        specs = [item(specified=50, margin_main_start=10), item(specified=50)]
        self.assertEqual([10, 60], positions(specs))
        spec = container(justify_content="flex-end")
        self.assertEqual([200, 250], positions(specs, spec))


class CrossAxisAlignmentTest(TestCase):
    """9.4 and 9.6, align-items, align-self, stretch and align-content."""

    @staticmethod
    def _measure(index, _main):
        return 40.0 if index == 0 else 20.0

    def test_stretch_gives_every_item_the_line_cross_size(self) -> None:
        specs = [item(specified=50), item(specified=50)]
        result = layout(specs, container(), self._measure)
        self.assertEqual([40, 40], [p.cross_size for p in result.placed])
        self.assertEqual(40, result.cross_size)

    def test_align_self_overrides_align_items(self) -> None:
        specs = [item(specified=50), item(specified=50, align_self="flex-end")]
        spec = container(align_items="flex-start")
        result = layout(specs, spec, self._measure)
        self.assertEqual([0, 20], [p.cross_pos for p in result.placed])
        self.assertEqual([40, 20], [p.cross_size for p in result.placed])

    def test_center(self) -> None:
        specs = [item(specified=50), item(specified=50, align_self="center")]
        result = layout(specs, container(), self._measure)
        self.assertEqual(10, result.placed[1].cross_pos)

    def test_a_declared_cross_size_is_not_stretched(self) -> None:
        specs = [item(specified=50), item(specified=50, cross_specified=15)]
        result = layout(specs, container(), self._measure)
        self.assertEqual(15, result.placed[1].cross_size)

    def test_cross_auto_margins_center_the_item(self) -> None:
        specs = [
            item(specified=50),
            item(specified=50, margin_cross_start=None, margin_cross_end=None),
        ]
        result = layout(specs, container(), self._measure)
        self.assertEqual(10, result.placed[1].cross_pos)
        self.assertEqual(20, result.placed[1].cross_size)

    def test_single_line_takes_the_definite_cross_size(self) -> None:
        specs = [item(specified=50)]
        result = layout(specs, container(cross=100), self._measure)
        self.assertEqual(100, result.lines[0].cross_size)
        self.assertEqual(100, result.placed[0].cross_size)

    def test_align_content_is_a_no_op_with_an_indefinite_cross_size(self) -> None:
        specs = [item(specified=200) for _ in range(2)]
        spec = container(300, wrap="wrap", align_content="center")
        result = layout(specs, spec)
        self.assertEqual([0, 20], [line.cross_pos for line in result.lines])
        self.assertEqual(40, result.cross_size)

    def test_align_content_center_with_a_definite_cross_size(self) -> None:
        specs = [item(specified=200) for _ in range(2)]
        spec = container(300, cross=100, wrap="wrap", align_content="center")
        result = layout(specs, spec)
        self.assertEqual([30, 50], [line.cross_pos for line in result.lines])

    def test_align_content_stretch_grows_the_lines(self) -> None:
        specs = [item(specified=200) for _ in range(2)]
        spec = container(300, cross=100, wrap="wrap")
        result = layout(specs, spec)
        self.assertEqual([50, 50], [line.cross_size for line in result.lines])
        self.assertEqual([50, 50], [p.cross_size for p in result.placed])


class OrderAndDirectionTest(TestCase):
    def test_order_reorders_layout_but_placed_items_keep_source_indices(self) -> None:
        specs = [item(specified=50, order=2), item(specified=50, order=1)]
        result = layout(specs)
        self.assertEqual([0, 1], [p.index for p in result.placed])
        self.assertEqual([50, 0], positions(specs))

    def test_row_reverse_mirrors_positions(self) -> None:
        specs = [item(specified=50), item(specified=50)]
        self.assertEqual(
            [250, 200], positions(specs, container(direction="row-reverse"))
        )

    def test_row_reverse_with_flex_end_packs_to_the_left(self) -> None:
        specs = [item(specified=50), item(specified=50)]
        spec = container(direction="row-reverse", justify_content="flex-end")
        self.assertEqual([50, 0], positions(specs, spec))

    def test_column_without_height_is_its_content(self) -> None:
        specs = [item(specified=30, grow=1), item(specified=40, grow=1)]
        spec = ContainerSpec(main_size=None, cross_size=200, direction="column")
        result = layout(specs, spec)
        self.assertEqual(70, result.main_size)
        self.assertEqual([30, 40], sizes(specs, spec))
        self.assertEqual([0, 30], positions(specs, spec))

    def test_column_with_a_height_distributes_it(self) -> None:
        specs = [item(specified=30, grow=1), item(specified=40, grow=1)]
        spec = ContainerSpec(main_size=170, cross_size=200, direction="column")
        self.assertEqual([80, 90], sizes(specs, spec))

    def test_no_items_is_an_empty_box(self) -> None:
        result = layout([], container(300, cross=50))
        self.assertEqual([], result.placed)
        self.assertEqual((300, 50), (result.main_size, result.cross_size))
