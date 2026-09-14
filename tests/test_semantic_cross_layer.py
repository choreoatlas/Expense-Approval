import tempfile, unittest
from pathlib import Path
from expense.store import ExpenseStore
class CrossLayerSemanticEvidence(unittest.TestCase):
 def setUp(self): self.t=tempfile.TemporaryDirectory(); self.db=Path(self.t.name)/'e.sqlite3'; self.s=ExpenseStore(self.db)
 def tearDown(self): self.t.cleanup()
 def test_high_value_direct_gm_and_persists(self):
  x=self.s.create_draft('alice','1000','Laptop','r1'); self.s.submit(x.expense_id)
  with self.assertRaises(PermissionError): self.s.decide(x.expense_id,1,'bob','approved','normal first stage')
  self.assertEqual('submitted',self.s.latest(x.expense_id).status.value)
  d=self.s.decide(x.expense_id,1,'carol','approved','high value GM approval')
  self.assertEqual('general_manager',d.actor_role); self.assertEqual('approved',self.s.latest(x.expense_id).status.value)
  reopened=ExpenseStore(self.db)
  self.assertEqual('approved',reopened.latest(x.expense_id).status.value)
  self.assertEqual(['general_manager'],[d['actor_role'] for d in reopened.history(x.expense_id)['decisions']])
 def test_below_threshold_keeps_two_stage(self):
  x=self.s.create_draft('alice','999.99','Taxi','r2'); self.s.submit(x.expense_id)
  self.s.decide(x.expense_id,1,'bob','approved','stage1'); self.assertEqual('manager_pending',self.s.latest(x.expense_id).status.value)
  self.s.decide(x.expense_id,1,'carol','approved','stage2'); self.assertEqual('approved',self.s.latest(x.expense_id).status.value)
if __name__=='__main__': unittest.main()
