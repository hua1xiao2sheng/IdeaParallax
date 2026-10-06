import asyncio
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from contextlib import contextmanager
from idea_parallax.cli import main
from idea_parallax.config import provider_config, validate_config
from idea_parallax.contracts import BATCH_SCHEMA
from idea_parallax.engine import Engine
from idea_parallax.io_utils import ValidationError, canonical, parse_model_json, write_json
from idea_parallax.providers import Provider, ProviderError
from helpers import brief, config, batch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from publish_github import allowed_path, release_files, publish, PublishError, TOP_FILES

@contextmanager
def http_fixture(response, status=200, headers=None):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append({'path':self.path,'headers':dict(self.headers),'body':json.loads(self.rfile.read(int(self.headers['Content-Length'])))})
            body=json.dumps(response).encode()
            self.send_response(status)
            for k,v in (headers or {}).items():self.send_header(k,v)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.02},daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}/v1',requests
    finally:server.shutdown();server.server_close();thread.join(timeout=2)

class DeliveryContracts(unittest.TestCase):
    def test_duplicate_json_keys_refused(self):
        with self.assertRaises(ValidationError):parse_model_json('{"hypothesis":"A","hypothesis":"B"}')
    def test_native_global_provider_not_reused_as_reviewer(self):
        c=config();c.pop('reviewer',None)
        c['provider']={'type':'native-codex','repository_path':'/repo','commit':'a'*40,'entry':'SKILL.md'}
        self.assertEqual(validate_config(c)['reviewer']['type'],'codex')
    def test_native_moving_commit_refused(self):
        with self.assertRaises(ValidationError):provider_config({'type':'native-codex','repository_path':'/repo','commit':'main','entry':'SKILL.md'})
    def test_packaging_contains_six_prompts(self):
        from importlib.resources import files
        self.assertEqual(len(list(files('idea_parallax').joinpath('data/strategies').iterdir())),6)
    def test_demo_overrides_real_provider_and_retrieval(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);cfg=config();cfg['provider']={'type':'api','model':'CHANGE_ME'};cfg['branches'][0]['provider']={'type':'native-codex'}
            write_json(d/'config.json',cfg)
            with patch('idea_parallax.engine.search_crossref',side_effect=AssertionError('demo must not use network')):
                self.assertEqual(main(['demo','--config',str(d/'config.json'),'--out',str(d/'run'),'--retrieval','crossref']),0)
    def test_cli_requires_real_brief(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(['run','--out',str(Path(d)/'run')]),1)

class Protocols(unittest.IsolatedAsyncioTestCase):
    async def test_api_protocol_over_local_http_server(self):
        response={'choices':[{'message':{'content':canonical(batch())},'finish_reason':'stop'}],'usage':{'prompt_tokens':11,'completion_tokens':12}}
        with http_fixture(response) as (url,requests), tempfile.TemporaryDirectory() as d:
            p=Provider(provider_config({'type':'api','model':'fixture-model','base_url':url}))
            result,usage=await p.complete('generate',{'brief':brief()},BATCH_SCHEMA,Path(d))
        self.assertEqual(result,batch());self.assertEqual(usage['prompt_tokens'],11)
        self.assertEqual(requests[0]['path'],'/v1/chat/completions')
        self.assertNotIn('Authorization',requests[0]['headers'])
    async def test_api_truncation_reported(self):
        response={'choices':[{'message':{'content':'{}'},'finish_reason':'length'}]}
        with http_fixture(response) as (url,_),tempfile.TemporaryDirectory() as d:
            p=Provider(provider_config({'type':'api','model':'fixture','base_url':url}))
            with self.assertRaisesRegex(ProviderError,'truncated'):await p.complete('generate',{},BATCH_SCHEMA,Path(d))
    async def test_api_error_body_not_disclosed(self):
        with http_fixture({'secret':'should-not-be-logged'},status=401) as (url,_),tempfile.TemporaryDirectory() as d:
            p=Provider(provider_config({'type':'api','model':'fixture','base_url':url}))
            with self.assertRaises(ProviderError) as caught:await p.complete('generate',{},BATCH_SCHEMA,Path(d))
            self.assertNotIn('should-not-be-logged',str(caught.exception))
    async def test_api_redirect_refused(self):
        with http_fixture({},status=307,headers={'Location':'https://example.invalid/leak'}) as (url,_),tempfile.TemporaryDirectory() as d:
            p=Provider(provider_config({'type':'api','model':'fixture','base_url':url}))
            with self.assertRaises(ProviderError):await p.complete('generate',{},BATCH_SCHEMA,Path(d))
    async def test_negative_usage_not_accepted(self):
        response={'choices':[{'message':{'content':canonical(batch())}}],'usage':{'prompt_tokens':-1,'completion_tokens':True}}
        with http_fixture(response) as (url,_),tempfile.TemporaryDirectory() as d:
            p=Provider(provider_config({'type':'api','model':'fixture','base_url':url}))
            _,usage=await p.complete('generate',{},BATCH_SCHEMA,Path(d))
        self.assertEqual(usage,{})
    async def test_external_adapter_real_subprocess(self):
        code='import sys,json; p=json.load(sys.stdin); assert p["task"]=="generate"; print('+repr(canonical(batch()))+')'
        with tempfile.TemporaryDirectory() as d:
            p=Provider(provider_config({'type':'command','command':[sys.executable,'-c',code]}),True)
            result,_=await p.complete('generate',{},BATCH_SCHEMA,Path(d))
        self.assertEqual(result,batch())
    async def test_codex_documented_command_and_usage(self):
        seen=[]
        async def fake(command,stdin,cwd,timeout,env):
            seen.append(command)
            write_json(Path(command[command.index('--output-last-message')+1]),batch())
            return '{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":9}}',''
        with tempfile.TemporaryDirectory() as d,patch('idea_parallax.providers.run_process',fake):
            out,usage=await Provider(provider_config({'type':'codex'})).complete('generate',{},BATCH_SCHEMA,Path(d))
        self.assertEqual(out,batch());self.assertEqual(usage['input_tokens'],7)
        self.assertIn('--ephemeral',seen[0]);self.assertIn('read-only',seen[0]);self.assertNotIn('--yolo',seen[0])
    async def test_retrieval_failure_marks_partial_not_novel(self):
        with tempfile.TemporaryDirectory() as d,patch('idea_parallax.engine.search_crossref',side_effect=ProviderError('offline')):
            r=await Engine(brief(),config(),Path(d)/'run',retrieval='crossref').run()
        self.assertEqual(r['status'],'partial');self.assertEqual(r['retrieval_status'],'failed')
        for rev in r['reviews']:
            for a in rev['output']['assessments']:self.assertEqual(a['novelty'],'insufficient_evidence')
    async def test_native_execution_is_explicitly_gated(self):
        p=Provider(provider_config({'type':'native-codex','repository_path':'/repo','commit':'a'*40,'entry':'SKILL.md'}))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ProviderError,'--allow-commands'):await p.complete('generate',{},BATCH_SCHEMA,Path(d))

class PublishSafety(unittest.TestCase):
    def manifest(self,root):
        entries=[]
        for name in TOP_FILES:
            p=root/name;p.write_text('test file',encoding='utf-8');entries.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        write_json(root/'release-files.json',{'project':'IdeaParallax','files':entries})
    def test_sensitive_files_excluded(self):
        for name in ['runs/task/report.json','.env','configs/api.local.json','../README.md','/README.md','docs/key.pem','idea_parallax/__pycache__/x.pyc']:
            self.assertFalse(allowed_path(name),name)
    def test_release_docs_allowed(self):
        self.assertTrue(allowed_path('docs/AUDIT.md'));self.assertTrue(allowed_path('.env.example'))
    def test_changed_file_refuses_publication(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.manifest(p);(p/'README.md').write_text('changed')
            with self.assertRaises(PublishError):release_files(p)
    def test_default_private_dry_run_creates_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.manifest(p)
            with patch('subprocess.run',side_effect=AssertionError('no actions in dry-run')):
                r=publish(p,'example-user')
            self.assertEqual(r['visibility'],'private');self.assertEqual(r['mode'],'dry_run')
    def test_missing_gh_does_not_claim_publish(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.manifest(p)
            with patch('shutil.which',return_value=None):
                with self.assertRaises(PublishError):publish(p,'example-user',execute=True)
    def test_unexpected_owner_characters_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PublishError):publish(Path(d),'a;bad')

class NativeHostProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_native_snapshot_and_host_contract(self):
        captured=[]
        async def fake(command,stdin,cwd,timeout,env):
            self.assertTrue((cwd/'SKILL.md').is_file())
            self.assertFalse((cwd/'.git').exists())
            self.assertIn('workspace-write',command)
            self.assertNotIn('sandbox_workspace_write.network_access=true',command)
            self.assertNotIn('PORT_SENTINEL',stdin)
            self.assertIn('native_workflow',stdin)
            captured.append(str(cwd))
            write_json(Path(command[command.index('--output-last-message')+1]),batch())
            return '{"type":"turn.completed","usage":{"input_tokens":1}}',''
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);repo=root/'repo';repo.mkdir();workspace=root/'call';workspace.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            (repo/'SKILL.md').write_text('# Actual pinned entry fixture\n')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
            sha=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            p=Provider(provider_config({'type':'native-codex','repository_path':str(repo),'commit':sha,'entry':'SKILL.md'}),True)
            with patch('idea_parallax.providers.run_process',fake):
                result,usage=await p.complete('generate',{'strategy_instructions':'PORT_SENTINEL'},BATCH_SCHEMA,workspace)
            self.assertEqual(result,batch());self.assertEqual(usage['native_commit'],sha)
            self.assertEqual(usage['step_attestation'],'not_verified')
            self.assertNotEqual(captured,[str(repo)])
