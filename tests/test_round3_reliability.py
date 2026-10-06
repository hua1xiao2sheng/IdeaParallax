import asyncio
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import contextmanager
from idea_parallax.engine import Engine, run_lock
from idea_parallax.io_utils import ValidationError, write_json, load_json
from idea_parallax.providers import Provider, ProviderError
from helpers import brief, config

class Reliability(unittest.IsolatedAsyncioTestCase):
    async def test_partial_failure_preserves_other_branches(self):
        class OneFail(Provider):
            async def complete(self, kind, payload, schema, workspace):
                if kind=='generate' and payload['strategy_id']=='aris': raise ProviderError('test failure')
                return await super().complete(kind,payload,schema,workspace)
        with tempfile.TemporaryDirectory() as d:
            r=await Engine(brief(),config(),Path(d)/'run',provider_factory=OneFail).run()
        self.assertEqual(r['status'],'partial'); self.assertEqual(len(r['candidates']),5)
    async def test_all_fail_never_falls_back_to_demo(self):
        class Fail(Provider):
            async def complete(self,*args): raise ProviderError('unavailable')
        with tempfile.TemporaryDirectory() as d:
            r=await Engine(brief(),config(),Path(d)/'run',provider_factory=Fail).run()
        self.assertEqual(r['status'],'failed'); self.assertEqual(r['candidates'],[])
    async def test_budget_is_global_and_hard_for_outer_calls(self):
        c=config();c['max_calls']=2;c['review']=False
        with tempfile.TemporaryDirectory() as d:
            r=await Engine(brief(),c,Path(d)/'run').run()
        self.assertEqual(r['budget']['calls_reserved'],2);self.assertEqual(len(r['candidates']),2)
    async def test_retry_counts_against_budget(self):
        count=0
        class FirstBad(Provider):
            async def complete(self,*args):
                nonlocal count
                count+=1
                if count==1: return {},{}
                return await super().complete(*args)
        c=config();c['branches']=c['branches'][:1];c['review']=False;c['retries']=1
        with tempfile.TemporaryDirectory() as d:
            r=await Engine(brief(),c,Path(d)/'run',provider_factory=FirstBad).run()
        self.assertEqual(r['status'],'completed');self.assertEqual(r['budget']['calls_reserved'],2)
    async def test_failed_branch_resume_only_retries_failed_generation(self):
        seen=[]
        class FirstFail(Provider):
            async def complete(self,kind,payload,schema,workspace):
                if kind=='generate' and payload['strategy_id']=='aris':raise ProviderError('first failure')
                return await super().complete(kind,payload,schema,workspace)
        class Record(Provider):
            async def complete(self,kind,payload,schema,workspace):
                if kind=='generate':seen.append(payload['strategy_id'])
                return await super().complete(kind,payload,schema,workspace)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run'
            await Engine(brief(),config(),root,provider_factory=FirstFail).run()
            r=await Engine(brief(),config(),root,provider_factory=Record).run(resume=True)
        self.assertEqual(seen,['aris']);self.assertEqual(r['status'],'completed')
        self.assertEqual(r['budget']['calls_reserved'],11)
    async def test_checkpoint_tampering_is_not_silently_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';await Engine(brief(),config(),root).run()
            path=root/'stages/generate-aris/result.json';raw=load_json(path);raw['output']['notes']='changed';write_json(path,raw)
            with self.assertRaises(ValidationError):await Engine(brief(),config(),root).run(resume=True)
    async def test_negative_saved_budget_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';await Engine(brief(),config(),root).run()
            path=root/'state.json';raw=load_json(path);raw['calls_reserved']=-1;write_json(path,raw)
            with self.assertRaises(ValidationError):await Engine(brief(),config(),root).run(resume=True)
    async def test_changed_brief_refuses_resume(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';await Engine(brief(),config(),root).run()
            with self.assertRaises(ValidationError):await Engine({'topic':'another'},config(),root).run(resume=True)
    async def test_two_reviewers_can_run_in_parallel(self):
        active=0;peak=0
        class Record(Provider):
            async def complete(self,kind,payload,schema,workspace):
                nonlocal active,peak
                if kind=='review':active+=1;peak=max(peak,active);await asyncio.sleep(.02)
                result=await super().complete(kind,payload,schema,workspace)
                if kind=='review':active-=1
                return result
        with tempfile.TemporaryDirectory() as d:
            await Engine(brief(),config(),Path(d)/'run',provider_factory=Record).run()
        self.assertEqual(peak,2)
    async def test_cancellation_records_interrupted_and_releases_lock(self):
        class Slow(Provider):
            async def complete(self,*args):await asyncio.sleep(10)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';task=asyncio.create_task(Engine(brief(),config(),root,provider_factory=Slow).run())
            await asyncio.sleep(.03);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertFalse((root/'.lock').exists())
            self.assertEqual(load_json(root/'state.json')['status'],'interrupted')
    async def test_race_rechecks_output_under_lock(self):
        @contextmanager
        def raced(root):
            write_json(root/'manifest.json',{'from_other_process':True})
            yield
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run'
            with patch('idea_parallax.engine.run_lock',raced):
                with self.assertRaises(ValidationError):await Engine(brief(),config(),root).run()
            self.assertEqual(load_json(root/'manifest.json'),{'from_other_process':True})
    async def test_no_review_mode(self):
        c=config();c['review']=False
        with tempfile.TemporaryDirectory() as d:
            r=await Engine(brief(),c,Path(d)/'run').run()
        self.assertEqual(r['reviews'],[]);self.assertEqual(r['budget']['calls_reserved'],6)

class Locks(unittest.TestCase):
    def test_active_lock_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with run_lock(Path(d)):
                with self.assertRaises(ValidationError):
                    with run_lock(Path(d)):pass
    def test_lock_released_on_failure(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                with run_lock(Path(d)):raise ValueError('test')
            self.assertFalse((Path(d)/'.lock').exists())
