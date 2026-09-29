"""Bounded, isolated and non-sliding series metadata reuse."""
import unittest

from tagger_volume_cache import VolumeCache, context, TTL, MAX_BYTES, MAX_ENTRIES


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.cache = VolumeCache(clock=lambda: self.now)
        self.key = context('https://example.com/api', 'private-key', True, '456')
        self.volume = {'id':456, 'name':'Series', 'publisher':{'name':'Publisher'}}

    def test_context_separates_endpoint_credentials_tls_and_identity(self):
        self.assertNotIn('private-key', repr(self.key))
        self.assertEqual(self.key, context('https://example.com/api/', 'private-key', True, 456))
        for args in [('https://other.example/api','private-key',True,'456'),
                     ('https://example.com/api','another',True,'456'),
                     ('https://example.com/api','private-key',False,'456'),
                     ('https://example.com/api','private-key',True,'457')]:
            self.assertNotEqual(self.key, context(*args))

    def test_copies_are_isolated_and_hits_do_not_renew_deadline(self):
        self.assertTrue(self.cache.put(self.key, self.volume, self.now + TTL))
        self.volume['publisher']['name'] = 'Mutated'
        item = self.cache.get(self.key)
        self.assertEqual(item['volume']['publisher']['name'], 'Publisher')
        item['volume']['name'] = 'Other'
        self.now += TTL - 1
        self.assertEqual(self.cache.get(self.key)['volume']['name'], 'Series')
        self.now += 1
        self.assertIsNone(self.cache.get(self.key))

    def test_expired_future_invalid_and_oversized_entries_are_not_retained(self):
        for deadline in [self.now, self.now-1, self.now+TTL+1, float('nan'), True, 'later']:
            self.assertFalse(self.cache.put(self.key, self.volume, deadline))
        for volume in [None, [], {'name':'x'*MAX_BYTES}, {'id':float('nan')}]:
            self.assertFalse(self.cache.put(self.key, volume, self.now+TTL))
        self.assertIsNone(self.cache.get(self.key))

    def test_capacity_and_least_recently_used_eviction(self):
        for index in range(MAX_ENTRIES):
            self.assertTrue(self.cache.put(str(index), self.volume, self.now+TTL))
        self.cache.get('0')
        self.cache.put('new', self.volume, self.now+TTL)
        self.assertIsNone(self.cache.get('1'))
        self.assertIsNotNone(self.cache.get('0'))
        self.assertEqual(len(self.cache.entries), MAX_ENTRIES)


if __name__ == '__main__':
    unittest.main()
