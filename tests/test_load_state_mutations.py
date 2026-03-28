"""
Tests for load_state_mutations.py

Covers:
- add_content_to_load: basic add, merging, capacity validation, UoM allowlist
- remove_content_from_load: exact removal, fractional splitting, under-stock error
"""
import unittest

from coopstorage.storage2.loc_load.dcs import (
    Load, LoadContent, UoMCapacity, UnitOfMeasure, Resource
)
from coopstorage.storage2.loc_load.load_state_mutations import (
    add_content_to_load,
    remove_content_from_load,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

EACH = UnitOfMeasure(name="EA")
BOX  = UnitOfMeasure(name="BOX")
SKU_A = Resource(name="SKU_A")
SKU_B = Resource(name="SKU_B")

def _load(uom_capacities=frozenset(), contents=frozenset()):
    return Load(id="L1", uom_capacities=uom_capacities, contents=contents)

def _content(resource=SKU_A, uom=EACH, qty=1.0):
    return LoadContent(resource=resource, uom=uom, qty=qty)


# ── add_content_to_load ───────────────────────────────────────────────────────

class TestAddContentToLoad(unittest.TestCase):

    def test_add_single_content_no_capacity(self):
        """No capacity defined → any UoM accepted, no qty limit."""
        load = _load()
        result = add_content_to_load(load, [_content(qty=5.0)])
        self.assertEqual(len(result.contents), 1)
        item = next(iter(result.contents))
        self.assertEqual(item.qty, 5.0)
        self.assertEqual(item.resource, SKU_A)

    def test_add_multiple_contents_merges_same_resource_uom(self):
        """Two adds of the same (resource, uom) should merge into one entry."""
        load = _load()
        load = add_content_to_load(load, [_content(qty=3.0)])
        load = add_content_to_load(load, [_content(qty=4.0)])
        self.assertEqual(len(load.contents), 1)
        item = next(iter(load.contents))
        self.assertEqual(item.qty, 7.0)

    def test_add_different_resources_stays_separate(self):
        """Different resources should be stored as separate content entries."""
        load = _load()
        load = add_content_to_load(load, [_content(resource=SKU_A, qty=2.0)])
        load = add_content_to_load(load, [_content(resource=SKU_B, qty=3.0)])
        self.assertEqual(len(load.contents), 2)
        total = sum(c.qty for c in load.contents)
        self.assertAlmostEqual(total, 5.0)

    def test_add_content_within_capacity(self):
        """Qty fits within defined UoM capacity."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        load = _load(uom_capacities=caps)
        result = add_content_to_load(load, [_content(qty=7.0)])
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 7.0)

    def test_add_content_exactly_at_capacity(self):
        """Qty exactly equals capacity — should succeed."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        load = _load(uom_capacities=caps)
        result = add_content_to_load(load, [_content(qty=10.0)])
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 10.0)

    def test_add_content_exceeds_capacity_raises(self):
        """Qty exceeds defined capacity → ValueError."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        load = _load(uom_capacities=caps)
        with self.assertRaises(ValueError):
            add_content_to_load(load, [_content(qty=11.0)])

    def test_add_content_cumulative_exceeds_capacity_raises(self):
        """Second add pushes total past capacity → ValueError."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        load = _load(uom_capacities=caps)
        load = add_content_to_load(load, [_content(qty=7.0)])
        with self.assertRaises(ValueError):
            add_content_to_load(load, [_content(qty=5.0)])

    def test_add_disallowed_uom_raises(self):
        """UoM not in uom_capacities → ValueError."""
        caps = frozenset([UoMCapacity(uom=BOX, capacity=5.0)])
        load = _load(uom_capacities=caps)
        with self.assertRaises(ValueError):
            add_content_to_load(load, [_content(uom=EACH, qty=1.0)])

    def test_add_content_returns_new_load_immutable(self):
        """Original load is not mutated; a new Load is returned."""
        load = _load()
        result = add_content_to_load(load, [_content(qty=1.0)])
        self.assertEqual(len(load.contents), 0)
        self.assertEqual(len(result.contents), 1)

    def test_negative_qty_raises_on_construction(self):
        """LoadContent with negative qty is invalid at construction time."""
        with self.assertRaises(ValueError):
            LoadContent(resource=SKU_A, uom=EACH, qty=-1.0)


# ── remove_content_from_load ──────────────────────────────────────────────────

class TestRemoveContentFromLoad(unittest.TestCase):

    def _load_with(self, qty):
        load = _load()
        return add_content_to_load(load, [_content(qty=qty)])

    def test_remove_exact_amount(self):
        """Remove exactly the amount present → contents empty."""
        load = self._load_with(5.0)
        result = remove_content_from_load(load, _content(qty=5.0))
        self.assertEqual(len(result.contents), 0)

    def test_remove_partial_amount(self):
        """Remove less than present → remainder correct."""
        load = self._load_with(10.0)
        result = remove_content_from_load(load, _content(qty=3.0))
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 7.0)

    def test_remove_fractional_split(self):
        """Remove a fractional amount from a whole-unit content item (splitting)."""
        load = _load()
        load = add_content_to_load(load, [_content(qty=7.5)])
        result = remove_content_from_load(load, _content(qty=2.5))
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 5.0)

    def test_remove_more_than_available_raises(self):
        """Removing more than available → ValueError."""
        load = self._load_with(3.0)
        with self.assertRaises(ValueError):
            remove_content_from_load(load, _content(qty=5.0))

    def test_remove_from_empty_load_raises(self):
        """Removing from a load with no contents → ValueError."""
        load = _load()
        with self.assertRaises(ValueError):
            remove_content_from_load(load, _content(qty=1.0))

    def test_remove_preserves_other_resources(self):
        """Removing SKU_A content doesn't affect SKU_B content."""
        load = _load()
        load = add_content_to_load(load, [_content(resource=SKU_A, qty=5.0)])
        load = add_content_to_load(load, [_content(resource=SKU_B, qty=8.0)])
        result = remove_content_from_load(load, _content(resource=SKU_A, qty=5.0))

        sku_b_items = [c for c in result.contents if c.resource == SKU_B]
        self.assertEqual(len(sku_b_items), 1)
        self.assertAlmostEqual(sku_b_items[0].qty, 8.0)
        sku_a_items = [c for c in result.contents if c.resource == SKU_A]
        self.assertEqual(len(sku_a_items), 0)

    def test_remove_returns_new_load_immutable(self):
        """Original load is not mutated."""
        load = self._load_with(10.0)
        _ = remove_content_from_load(load, _content(qty=3.0))
        original_qty = next(iter(load.contents)).qty
        self.assertAlmostEqual(original_qty, 10.0)

    def test_verification_after_remove(self):
        """After removal, qty_before - qty_removed == qty_after."""
        load = self._load_with(10.0)
        qty_before = next(iter(load.contents)).qty
        qty_to_remove = 4.0
        result = remove_content_from_load(load, _content(qty=qty_to_remove))
        qty_after = next(iter(result.contents)).qty
        self.assertAlmostEqual(qty_before - qty_to_remove, qty_after)


if __name__ == "__main__":
    unittest.main()
