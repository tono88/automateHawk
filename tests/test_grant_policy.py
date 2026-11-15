import os,unittest
from unittest.mock import patch
from app.scoped_repository import read_grant_minutes


class GrantPolicyTests(unittest.TestCase):
    def test_default_lifetimes_and_explicit_bounds(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(read_grant_minutes('HUB_LIST_GRANT_MINUTES',60),60)
            self.assertEqual(read_grant_minutes('HUB_DETAIL_GRANT_MINUTES',30),30)
        for value in ('15','480'):
            with patch.dict(os.environ,{'HUB_DETAIL_GRANT_MINUTES':value}):
                self.assertEqual(read_grant_minutes('HUB_DETAIL_GRANT_MINUTES',30),int(value))
        for value in ('0','14','481','eight','30.5'):
            with patch.dict(os.environ,{'HUB_DETAIL_GRANT_MINUTES':value}),self.assertRaises(ValueError):
                read_grant_minutes('HUB_DETAIL_GRANT_MINUTES',30)
