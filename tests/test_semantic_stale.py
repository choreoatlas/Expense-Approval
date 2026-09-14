import unittest
from semantic_stale_trial import Judgment, rejudge

class SemanticRevisionStaleEvidence(unittest.TestCase):
    def test_threshold_revision_only_stales_affected_judgments(self):
        judgments = [
            Judgment(1, '500', ('bob:approved','carol:approved'), 'threshold=1000'),
            Judgment(2, '800', ('bob:approved','carol:approved'), 'threshold=1000'),
            Judgment(3, '1200', ('carol:approved',), 'threshold=1000'),
        ]
        out = [rejudge(j, '1000', '750') for j in judgments]
        self.assertEqual(['ACCEPTED','STALE','ACCEPTED'], [j.state for j in out])
        self.assertIn("('approver', 'general_manager') -> ('general_manager',)", out[1].reason)

    def test_stale_old_evidence_cannot_close_under_new_semantics(self):
        old = Judgment(8, '800', ('bob:approved','carol:approved'), 'threshold=1000')
        revised = rejudge(old, '1000', '750')
        self.assertEqual('STALE', revised.state)
        self.assertNotEqual(('carol:approved',), revised.evidence)

if __name__ == '__main__': unittest.main()
