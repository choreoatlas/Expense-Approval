from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EffectiveState:
    expense_id: int
    expense_revision: int
    semantic_id: str
    semantic_revision: int
    state: str
    judgment_state: str | None


class CloseLoopRuntime:
    SEMANTIC_ID = 'SEM-EXP-AUTHORITY'

    def __init__(self, store):
        self.store = store
        self._init_schema()

    def _init_schema(self):
        with self.store._connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS semantic_revisions(
              semantic_id TEXT NOT NULL, revision INTEGER NOT NULL,
              statement TEXT NOT NULL, threshold TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY(semantic_id, revision));
            CREATE TABLE IF NOT EXISTS evidence(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              expense_id INTEGER NOT NULL, expense_revision INTEGER NOT NULL,
              semantic_id TEXT NOT NULL, semantic_revision INTEGER NOT NULL,
              kind TEXT NOT NULL, payload TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS judgments(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              expense_id INTEGER NOT NULL, expense_revision INTEGER NOT NULL,
              semantic_id TEXT NOT NULL, semantic_revision INTEGER NOT NULL,
              state TEXT NOT NULL, reason TEXT NOT NULL,
              supersedes INTEGER,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            ''')
            c.execute('''INSERT OR IGNORE INTO semantic_revisions
              (semantic_id,revision,statement,threshold) VALUES (?,?,?,?)''',
              (self.SEMANTIC_ID, 1, 'High-value expenses require direct general-manager approval', '1000'))

    def current_semantic(self):
        with self.store._connect() as c:
            return c.execute('SELECT * FROM semantic_revisions WHERE semantic_id=? ORDER BY revision DESC LIMIT 1',
                             (self.SEMANTIC_ID,)).fetchone()

    def revise_threshold(self, threshold: str):
        Decimal(threshold)
        old = self.current_semantic()
        rev = old['revision'] + 1
        with self.store._connect() as c:
            c.execute('INSERT INTO semantic_revisions(semantic_id,revision,statement,threshold) VALUES (?,?,?,?)',
                      (self.SEMANTIC_ID, rev, old['statement'], str(threshold)))
            rows = c.execute('''SELECT j.id,j.expense_id,j.expense_revision,r.amount
              FROM judgments j JOIN revisions r ON r.expense_id=j.expense_id AND r.revision=j.expense_revision
              WHERE j.semantic_id=? AND j.state='ACCEPTED' AND j.semantic_revision=?''',
              (self.SEMANTIC_ID, old['revision'])).fetchall()
            for row in rows:
                old_path = self._path(row['amount'], old['threshold'])
                new_path = self._path(row['amount'], threshold)
                if old_path != new_path:
                    c.execute('''INSERT INTO judgments(expense_id,expense_revision,semantic_id,semantic_revision,state,reason,supersedes)
                      VALUES (?,?,?,?,?,?,?)''', (row['expense_id'],row['expense_revision'],self.SEMANTIC_ID,rev,'STALE',
                      f'authority path changed {old_path} -> {new_path}',row['id']))
        return rev

    @staticmethod
    def _path(amount, threshold):
        return ('general_manager',) if Decimal(amount) >= Decimal(threshold) else ('approver','general_manager')

    def capture_decision_evidence(self, decision):
        sem = self.current_semantic()
        with self.store._connect() as c:
            c.execute('''INSERT INTO evidence(expense_id,expense_revision,semantic_id,semantic_revision,kind,payload)
              VALUES (?,?,?,?,?,?)''', (decision.expense_id,decision.revision,self.SEMANTIC_ID,sem['revision'],'decision',json.dumps(decision.__dict__,sort_keys=True)))

    def judge(self, expense_id: int, expense_revision: int):
        sem = self.current_semantic()
        rev = self.store.get_revision(expense_id, expense_revision)
        expected = self._path(rev.content.amount, sem['threshold'])
        with self.store._connect() as c:
            rows = c.execute('''SELECT actor_role,outcome FROM decisions WHERE expense_id=? AND revision=? ORDER BY id''',
                             (expense_id,expense_revision)).fetchall()
            actual = tuple(r['actor_role'] for r in rows if r['outcome']=='approved')
            accepted = rev.status.value == 'approved' and actual == expected
            state = 'ACCEPTED' if accepted else 'REJECTED'
            reason = f'expected authority path {expected}; observed {actual}; status={rev.status.value}'
            c.execute('''INSERT INTO judgments(expense_id,expense_revision,semantic_id,semantic_revision,state,reason)
              VALUES (?,?,?,?,?,?)''', (expense_id,expense_revision,self.SEMANTIC_ID,sem['revision'],state,reason))
        return state

    def effective_state(self, expense_id: int, expense_revision: int):
        sem = self.current_semantic()
        with self.store._connect() as c:
            j = c.execute('''SELECT * FROM judgments WHERE expense_id=? AND expense_revision=? AND semantic_id=?
              ORDER BY id DESC LIMIT 1''', (expense_id,expense_revision,self.SEMANTIC_ID)).fetchone()
        if not j or j['semantic_revision'] != sem['revision'] or j['state'] == 'STALE':
            return EffectiveState(expense_id,expense_revision,self.SEMANTIC_ID,sem['revision'],'NEEDS_REJUDGMENT', None if not j else j['state'])
        return EffectiveState(expense_id,expense_revision,self.SEMANTIC_ID,sem['revision'],j['state'],j['state'])

    def ledger(self, expense_id: int):
        with self.store._connect() as c:
            return {
              'semantics':[dict(x) for x in c.execute('SELECT * FROM semantic_revisions ORDER BY revision')],
              'evidence':[dict(x) for x in c.execute('SELECT * FROM evidence WHERE expense_id=? ORDER BY id',(expense_id,))],
              'judgments':[dict(x) for x in c.execute('SELECT * FROM judgments WHERE expense_id=? ORDER BY id',(expense_id,))],
            }
