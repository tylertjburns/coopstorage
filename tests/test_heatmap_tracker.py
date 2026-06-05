import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from coopstorage.storage.api.routers.v1.heatmap_tracker import HeatmapTracker, HeatmapRecord


class TestHeatmapTrackerGetCounts(unittest.TestCase):

    def _make_tracker(self):
        storage = MagicMock()
        storage.get_locs.return_value = {}
        return HeatmapTracker(storage)

    def test_get_counts_returns_empty_when_no_records(self):
        tracker = self._make_tracker()
        self.assertEqual(tracker.get_counts(), {'location': {}, 'load': {}})

    def test_get_counts_separates_location_from_load(self):
        now = datetime.now(timezone.utc)
        tracker = self._make_tracker()
        tracker._records = [
            HeatmapRecord('loc1', 'location', now),
            HeatmapRecord('loc1', 'load',     now),
            HeatmapRecord('loc2', 'location', now),
        ]
        result = tracker.get_counts()
        self.assertEqual(result['location'], {'loc1': 1, 'loc2': 1})
        self.assertEqual(result['load'],     {'loc1': 1})

    def test_get_counts_no_filter_returns_all(self):
        now = datetime.now(timezone.utc)
        tracker = self._make_tracker()
        tracker._records = [
            HeatmapRecord('loc1', 'location', now - timedelta(minutes=i))
            for i in range(5)
        ]
        self.assertEqual(tracker.get_counts()['location']['loc1'], 5)

    def test_get_counts_filters_by_start_inclusive(self):
        now = datetime.now(timezone.utc)
        tracker = self._make_tracker()
        start = now - timedelta(minutes=5)
        tracker._records = [
            HeatmapRecord('loc1', 'location', now - timedelta(minutes=10)),  # excluded
            HeatmapRecord('loc1', 'location', start),                         # included (== boundary)
            HeatmapRecord('loc1', 'location', now),                           # included
        ]
        self.assertEqual(tracker.get_counts(start=start)['location']['loc1'], 2)

    def test_get_counts_filters_by_end_inclusive(self):
        now = datetime.now(timezone.utc)
        tracker = self._make_tracker()
        end = now - timedelta(minutes=1)
        tracker._records = [
            HeatmapRecord('loc1', 'location', now - timedelta(minutes=2)),  # included
            HeatmapRecord('loc1', 'location', end),                          # included (== boundary)
            HeatmapRecord('loc1', 'location', now),                          # excluded
        ]
        self.assertEqual(tracker.get_counts(end=end)['location']['loc1'], 2)


if __name__ == '__main__':
    unittest.main()
