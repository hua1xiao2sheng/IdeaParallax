import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from idea_parallax.aggregation import aggregate
from idea_parallax.contracts import validate_batch, validate_review
from idea_parallax.demo import demo_output
from idea_parallax.io_utils import ValidationError, write_json, load_json
from idea_parallax.upstreams import import_bundle, read_bundle
from helpers import batch

def ideas():
    a=batch()['candidates'][0];a['id']='idea-one'
    b=copy.deepcopy(a);b['id']='idea-two'
    return a,b

def review():
    a,b=ideas()
    return demo_output('review',{'candidates':[a,b]})

class Integrity(unittest.TestCase):
    def test_identical_science_different_title_grouped_without_deletion(self):
        a,b=ideas();b['title']='another title';r=aggregate([a,b])
        self.assertEqual(r['family_count'],1);self.assertEqual(r['raw_count'],2);self.assertEqual(r['deletions'],0)
    def test_different_hypothesis_preserved(self):
        a,b=ideas();b['hypothesis']='Opposite hypothesis'
        self.assertEqual(aggregate([a,b])['family_count'],2)
    def test_different_falsification_preserved(self):
        a,b=ideas();b['experiment']['falsification']='Different disconfirmation'
        self.assertEqual(aggregate([a,b])['family_count'],2)
    def test_different_experimental_condition_preserved(self):
        a,b=ideas();b['experiment']['baseline']='A different controlled baseline'
        self.assertEqual(aggregate([a,b])['family_count'],2)
    def test_metadata_cannot_establish_novelty(self):
        r=review()
        for x in r['assessments']:x['novelty']='difference_to_investigate';x['evidence_ids']=['crossref-1']
        out=validate_review(r,{'idea-one','idea-two'},{'crossref-1'},True)
        self.assertTrue(all(x['novelty']=='insufficient_evidence' for x in out['assessments']))
    def test_validation_does_not_rewrite_raw_review(self):
        r=review();r['assessments'][0]['novelty']='difference_to_investigate';original=copy.deepcopy(r)
        validate_review(r,{'idea-one','idea-two'},set(),True)
        self.assertEqual(r,original)
    def test_unknown_review_evidence_refused(self):
        r=review();r['assessments'][0]['evidence_ids']=['made-up']
        with self.assertRaises(ValidationError):validate_review(r,{'idea-one','idea-two'},set(),True)
    def test_missing_candidate_review_refused(self):
        r=review();r['assessments'].pop()
        with self.assertRaises(ValidationError):validate_review(r,{'idea-one','idea-two'},set(),True)
    def test_duplicate_candidate_review_refused(self):
        r=review();r['assessments'][1]['idea_id']='idea-one'
        with self.assertRaises(ValidationError):validate_review(r,{'idea-one','idea-two'},set(),True)
    def test_global_novelty_claim_not_a_valid_status(self):
        r=review();r['assessments'][0]['novelty']='globally_novel'
        with self.assertRaises(ValidationError):validate_review(r,{'idea-one','idea-two'},set(),False)
    def test_zero_candidates_need_reason(self):
        with self.assertRaises(ValidationError):validate_batch({'candidates':[],'notes':''},set(),3)
    def test_empty_search_query_refused(self):
        r=batch();r['candidates'][0]['search_queries']=['  ']
        with self.assertRaises(ValidationError):validate_batch(r,set(),3)
    def test_no_experiment_results_in_contract(self):
        r=batch();r['candidates'][0]['results']={'accuracy':0.99}
        with self.assertRaises(ValidationError):validate_batch(r,set(),3)

class Upstreams(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        (self.repo/'SKILL.md').write_text('# a pinned test skill\n',encoding='utf-8')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
        self.sha=subprocess.check_output(['git','-C',str(self.repo),'rev-parse','HEAD'],text=True).strip()
    def tearDown(self):self.temp.cleanup()
    def test_pinned_text_import(self):
        out=self.root/'bundle.json';r=import_bundle(self.repo,self.sha,['SKILL.md'],out)
        self.assertEqual(read_bundle(out)['commit'],self.sha)
        self.assertIn('not_native',r['mode'])
    def test_moving_branch_refused(self):
        with self.assertRaises(ValidationError):import_bundle(self.repo,'main',['SKILL.md'],self.root/'x.json')
    def test_script_import_refused(self):
        with self.assertRaises(ValidationError):import_bundle(self.repo,self.sha,['run.py'],self.root/'x.json')
    def test_path_traversal_refused(self):
        with self.assertRaises(ValidationError):import_bundle(self.repo,self.sha,['../secret.md'],self.root/'x.json')
    def test_modified_bundle_refused(self):
        out=self.root/'bundle.json';import_bundle(self.repo,self.sha,['SKILL.md'],out)
        r=load_json(out);r['files'][0]['content']='tampered';write_json(out,r)
        with self.assertRaises(ValidationError):read_bundle(out)
    def test_existing_bundle_not_overwritten(self):
        out=self.root/'bundle.json';import_bundle(self.repo,self.sha,['SKILL.md'],out)
        with self.assertRaises(ValidationError):import_bundle(self.repo,self.sha,['SKILL.md'],out)
    def test_native_snapshot_does_not_modify_original(self):
        from idea_parallax.native import export_snapshot
        before=subprocess.check_output(['git','-C',str(self.repo),'status','--porcelain'])
        target=self.root/'snapshot';export_snapshot(self.repo,self.sha,target)
        self.assertEqual((target/'SKILL.md').read_text(),'# a pinned test skill\n')
        self.assertFalse((target/'.git').exists())
        self.assertEqual(subprocess.check_output(['git','-C',str(self.repo),'status','--porcelain']),before)
    def test_native_archive_rejects_symlinks(self):
        import os
        if os.name=='nt':self.skipTest('symlink privileges vary on Windows')
        from idea_parallax.native import export_snapshot
        (self.repo/'danger.md').symlink_to('/etc/passwd')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','symlink'],check=True)
        sha=subprocess.check_output(['git','-C',str(self.repo),'rev-parse','HEAD'],text=True).strip()
        with self.assertRaises(ValidationError):export_snapshot(self.repo,sha,self.root/'snapshot')
