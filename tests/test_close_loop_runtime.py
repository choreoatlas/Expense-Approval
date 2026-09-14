import tempfile, unittest
from pathlib import Path
from expense.store import ExpenseStore
from expense.close_loop_runtime import CloseLoopRuntime

class CloseLoopNativeRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.db=Path(self.t.name)/'e.sqlite3'
  self.s=ExpenseStore(self.db); self.cl=CloseLoopRuntime(self.s)
 def tearDown(self): self.t.cleanup()
 def approve_two_stage(self, amount='800'):
  x=self.s.create_draft('alice',amount,'Travel','r1'); self.s.submit(x.expense_id)
  d1=self.s.decide(x.expense_id,1,'bob','approved','stage1'); self.cl.capture_decision_evidence(d1)
  d2=self.s.decide(x.expense_id,1,'carol','approved','stage2'); self.cl.capture_decision_evidence(d2)
  return x.expense_id
 def test_semantic_evidence_judgment_effective_state_persist_in_same_sqlite(self):
  i=self.approve_two_stage('800')
  self.assertEqual('ACCEPTED',self.cl.judge(i,1))
  self.assertEqual('ACCEPTED',self.cl.effective_state(i,1).state)
  reopened=ExpenseStore(self.db); runtime=CloseLoopRuntime(reopened)
  self.assertEqual('ACCEPTED',runtime.effective_state(i,1).state)
  ledger=runtime.ledger(i)
  self.assertEqual(2,len(ledger['evidence'])); self.assertEqual('ACCEPTED',ledger['judgments'][-1]['state'])
 def test_semantic_revision_selectively_stales_old_judgment_without_deleting_evidence(self):
  low=self.approve_two_stage('500'); mid=self.approve_two_stage('800')
  self.cl.judge(low,1); self.cl.judge(mid,1)
  before=len(self.cl.ledger(mid)['evidence'])
  self.assertEqual(2,self.cl.revise_threshold('750'))
  self.assertEqual('NEEDS_REJUDGMENT',self.cl.effective_state(mid,1).state)
  self.assertEqual('NEEDS_REJUDGMENT',self.cl.effective_state(low,1).state)
  ledger=self.cl.ledger(mid)
  self.assertEqual(before,len(ledger['evidence']))
  self.assertEqual('STALE',ledger['judgments'][-1]['state'])
  self.assertIn('authority path changed',ledger['judgments'][-1]['reason'])
 def test_old_evidence_cannot_close_new_semantic_revision(self):
  i=self.approve_two_stage('800'); self.cl.judge(i,1); self.cl.revise_threshold('750')
  self.assertEqual('REJECTED',self.cl.judge(i,1))
  self.assertEqual('REJECTED',self.cl.effective_state(i,1).state)

if __name__=='__main__': unittest.main()
