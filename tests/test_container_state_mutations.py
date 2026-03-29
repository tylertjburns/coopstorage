"""
Tests for container_state_mutations.py

Covers:
- add_content_to_container: basic add, merging, capacity validation, UoM allowlist
- remove_content_from_container: exact removal, fractional splitting, under-stock error
"""
import unittest

from coopstorage.storage2.loc_load.dcs import (
    Container, ContainerContent, UoMCapacity, UnitOfMeasure, Resource
)
from coopstorage.storage2.loc_load.container_state_mutations import (
    add_content_to_container,
    remove_content_from_container,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

EACH = UnitOfMeasure(name="EA")
BOX  = UnitOfMeasure(name="BOX")
SKU_A = Resource(name="SKU_A")
SKU_B = Resource(name="SKU_B")

def _container(uom_capacities=frozenset(), contents=frozenset()):
    return Container(id="L1", uom_capacities=uom_capacities, contents=contents)

def _content(resource=SKU_A, uom=EACH, qty=1.0):
    return ContainerContent(resource=resource, uom=uom, qty=qty)


# ── add_content_to_container ──────────────────────────────────────────────────

class TestAddContentToContainer(unittest.TestCase):

    def test_add_single_content_no_capacity(self):
        """No capacity defined → any UoM accepted, no qty limit."""
        container = _container()
        result = add_content_to_container(container, [_content(qty=5.0)])
        self.assertEqual(len(result.contents), 1)
        item = next(iter(result.contents))
        self.assertEqual(item.qty, 5.0)
        self.assertEqual(item.resource, SKU_A)

    def test_add_multiple_contents_merges_same_resource_uom(self):
        """Two adds of the same (resource, uom) should merge into one entry."""
        container = _container()
        container = add_content_to_container(container, [_content(qty=3.0)])
        container = add_content_to_container(container, [_content(qty=4.0)])
        self.assertEqual(len(container.contents), 1)
        item = next(iter(container.contents))
        self.assertEqual(item.qty, 7.0)

    def test_add_different_resources_stays_separate(self):
        """Different resources should be stored as separate content entries."""
        container = _container()
        container = add_content_to_container(container, [_content(resource=SKU_A, qty=2.0)])
        container = add_content_to_container(container, [_content(resource=SKU_B, qty=3.0)])
        self.assertEqual(len(container.contents), 2)
        total = sum(c.qty for c in container.contents)
        self.assertAlmostEqual(total, 5.0)

    def test_add_content_within_capacity(self):
        """Qty fits within defined UoM capacity."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        container = _container(uom_capacities=caps)
        result = add_content_to_container(container, [_content(qty=7.0)])
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 7.0)

    def test_add_content_exactly_at_capacity(self):
        """Qty exactly equals capacity — should succeed."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        container = _container(uom_capacities=caps)
        result = add_content_to_container(container, [_content(qty=10.0)])
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 10.0)

    def test_add_content_exceeds_capacity_raises(self):
        """Qty exceeds defined capacity → ValueError."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        container = _container(uom_capacities=caps)
        with self.assertRaises(ValueError):
            add_content_to_container(container, [_content(qty=11.0)])

    def test_add_content_cumulative_exceeds_capacity_raises(self):
        """Second add pushes total past capacity → ValueError."""
        caps = frozenset([UoMCapacity(uom=EACH, capacity=10.0)])
        container = _container(uom_capacities=caps)
        container = add_content_to_container(container, [_content(qty=7.0)])
        with self.assertRaises(ValueError):
            add_content_to_container(container, [_content(qty=5.0)])

    def test_add_disallowed_uom_raises(self):
        """UoM not in uom_capacities → ValueError."""
        caps = frozenset([UoMCapacity(uom=BOX, capacity=5.0)])
        container = _container(uom_capacities=caps)
        with self.assertRaises(ValueError):
            add_content_to_container(container, [_content(uom=EACH, qty=1.0)])

    def test_add_content_returns_new_container_immutable(self):
        """Original container is not mutated; a new Container is returned."""
        container = _container()
        result = add_content_to_container(container, [_content(qty=1.0)])
        self.assertEqual(len(container.contents), 0)
        self.assertEqual(len(result.contents), 1)

    def test_negative_qty_raises_on_construction(self):
        """ContainerContent with negative qty is invalid at construction time."""
        with self.assertRaises(ValueError):
            ContainerContent(resource=SKU_A, uom=EACH, qty=-1.0)


# ── remove_content_from_container ─────────────────────────────────────────────

class TestRemoveContentFromContainer(unittest.TestCase):

    def _container_with(self, qty):
        container = _container()
        return add_content_to_container(container, [_content(qty=qty)])

    def test_remove_exact_amount(self):
        """Remove exactly the amount present → contents empty."""
        container = self._container_with(5.0)
        result = remove_content_from_container(container, _content(qty=5.0))
        self.assertEqual(len(result.contents), 0)

    def test_remove_partial_amount(self):
        """Remove less than present → remainder correct."""
        container = self._container_with(10.0)
        result = remove_content_from_container(container, _content(qty=3.0))
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 7.0)

    def test_remove_fractional_split(self):
        """Remove a fractional amount from a whole-unit content item (splitting)."""
        container = _container()
        container = add_content_to_container(container, [_content(qty=7.5)])
        result = remove_content_from_container(container, _content(qty=2.5))
        item = next(iter(result.contents))
        self.assertAlmostEqual(item.qty, 5.0)

    def test_remove_more_than_available_raises(self):
        """Removing more than available → ValueError."""
        container = self._container_with(3.0)
        with self.assertRaises(ValueError):
            remove_content_from_container(container, _content(qty=5.0))

    def test_remove_from_empty_container_raises(self):
        """Removing from a container with no contents → ValueError."""
        container = _container()
        with self.assertRaises(ValueError):
            remove_content_from_container(container, _content(qty=1.0))

    def test_remove_preserves_other_resources(self):
        """Removing SKU_A content doesn't affect SKU_B content."""
        container = _container()
        container = add_content_to_container(container, [_content(resource=SKU_A, qty=5.0)])
        container = add_content_to_container(container, [_content(resource=SKU_B, qty=8.0)])
        result = remove_content_from_container(container, _content(resource=SKU_A, qty=5.0))

        sku_b_items = [c for c in result.contents if c.resource == SKU_B]
        self.assertEqual(len(sku_b_items), 1)
        self.assertAlmostEqual(sku_b_items[0].qty, 8.0)
        sku_a_items = [c for c in result.contents if c.resource == SKU_A]
        self.assertEqual(len(sku_a_items), 0)

    def test_remove_returns_new_container_immutable(self):
        """Original container is not mutated."""
        container = self._container_with(10.0)
        _ = remove_content_from_container(container, _content(qty=3.0))
        original_qty = next(iter(container.contents)).qty
        self.assertAlmostEqual(original_qty, 10.0)

    def test_verification_after_remove(self):
        """After removal, qty_before - qty_removed == qty_after."""
        container = self._container_with(10.0)
        qty_before = next(iter(container.contents)).qty
        qty_to_remove = 4.0
        result = remove_content_from_container(container, _content(qty=qty_to_remove))
        qty_after = next(iter(result.contents)).qty
        self.assertAlmostEqual(qty_before - qty_to_remove, qty_after)


if __name__ == "__main__":
    unittest.main()
