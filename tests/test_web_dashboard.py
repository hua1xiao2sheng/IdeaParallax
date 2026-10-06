"""Dashboard tests are offline; no account, network search, or paid-model claims."""
import asyncio
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from idea_parallax.web import Dashboard, Server, make_task
from idea_parallax.io_utils import ValidationError, load_json
from idea_parallax.codex_host import check_codex, codex_command, subscription_env
from idea_parallax.providers import Provider
from idea_parallax.config import provider_config
from idea_parallax.demo import demo_output


def task(**kw):
    return {"mode": "demo", "brief": {"topic": "中文研究输入：寻找缺失证据", "context": "原始材料"}, **kw}


def wait_done(dash, ident, seconds=6):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        snap=dash.snapshot(ident)
        if not snap['active']:
            return snap
        time.sleep(.02)
    raise AssertionError('Dashboard job did not stop')


class WebContracts(unittest.TestCase):
    def test_subscription_only_configuration(self):
        spec=make_task(task(mode='codex',consent=True))
        self.assertTrue(spec['config']['provider']['subscription_only'])
        self.assertEqual(spec['config']['max_calls'],8)
        self.assertEqual(spec['config']['retries'],0)
        self.assertEqual(spec['config']['concurrency'],2)
    def test_minimal_run_calls(self):
        spec=make_task(task(strategies=['orchestra','aris'],review=False,max_ideas=1))
        self.assertEqual(spec['config']['max_calls'],2)
    def test_no_implicit_paid_use(self):
        with self.assertRaises(ValidationError):make_task(task(mode='codex'))
    def test_no_arbitrary_provider_from_browser(self):
        with self.assertRaises(ValidationError):make_task(task(provider={'type':'command'}))
    def test_no_arbitrary_binary_from_browser(self):
        with self.assertRaises(ValidationError):make_task(task(codex_binary='malicious'))
    def test_bad_mode(self):
        with self.assertRaises(ValidationError):make_task(task(mode='native-codex'))
    def test_unknown_and_duplicate_strategies(self):
        for keys in [[],['aris','aris'],['../../etc'],['not-real']]:
            with self.assertRaises(ValidationError):make_task(task(strategies=keys))
    def test_demo_disables_network(self):
        self.assertEqual(make_task(task(retrieval='crossref'))['retrieval'],'none')
    def test_brief_not_mutated(self):
        raw=task();raw['brief']['seed_papers']=[{'title':'Paper','excerpt':'研究原文'}]
        old=copy.deepcopy(raw);spec=make_task(raw)
        self.assertEqual(raw,old)
        self.assertNotIn('id',spec['brief']['seed_papers'][0])
    def test_subscription_flag_boolean(self):
        with self.assertRaises(ValidationError):provider_config({'type':'codex','subscription_only':'true'})
    def test_subscription_no_inherited_api_keys(self):
        import os
        with patch.dict(os.environ,{'OPENAI_API_KEY':'dummy','CODEX_API_KEY':'dummy'}):
            env=subscription_env();self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('CODEX_API_KEY',env)
    def test_auth_missing(self):
        with patch('idea_parallax.codex_host.shutil.which',return_value=None):
            self.assertFalse(check_codex()['chatgpt_login'])
    def test_auth_classification_never_returns_raw_text(self):
        from subprocess import CompletedProcess
        for stdout,status in [(b'Logged in using ChatGPT account-secret','chatgpt'),(b'Logged in using API key SECRET','api_key')]:
            with patch('idea_parallax.codex_host.codex_command',return_value=['codex']),patch('idea_parallax.codex_host.subprocess.run',return_value=CompletedProcess([],0,stdout,b'')):
                result=check_codex();self.assertEqual(result['status'],status);self.assertNotIn('SECRET',json.dumps(result));self.assertNotIn('account-secret',json.dumps(result))
    def test_windows_npm_shim_without_shell(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);shim=p/'codex.cmd';shim.write_text('@echo off',encoding='utf-8')
            entry=p/'node_modules/@openai/codex/bin/codex.js';entry.parent.mkdir(parents=True);entry.write_text('// fixture',encoding='utf-8')
            with patch('idea_parallax.codex_host.shutil.which',side_effect=[str(shim),'node.exe']):
                self.assertEqual(codex_command(),['node.exe',str(entry)])
    def test_unrecognized_shell_shim_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('idea_parallax.codex_host.shutil.which',side_effect=[str(Path(d)/'codex.cmd'),'node.exe']):
                with self.assertRaises(RuntimeError):codex_command()


class WebLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.dash=Dashboard(Path(self.temp.name)/'jobs')
    def tearDown(self):
        self.dash.close();self.temp.cleanup()
    def test_demo_persist_history_preview_and_export(self):
        ident=self.dash.start(task());snap=wait_done(self.dash,ident)
        self.assertEqual(snap['status'],'completed', snap);self.assertEqual(len(snap['candidates']),6)
        self.assertEqual(snap['calls'],8);self.assertTrue(snap['report_ready'])
        self.assertIn(b'SYNTHETIC DEMO',self.dash.export(ident,'report.html'))
        self.assertEqual(self.dash.history()[0]['id'],ident)
        self.assertEqual(len(snap['stages']),8)
    def test_path_traversal_refused(self):
        with self.assertRaises(ValidationError):self.dash.directory('../outside')
    def test_export_allowlist(self):
        ident=self.dash.start(task());wait_done(self.dash,ident)
        with self.assertRaises(ValidationError):self.dash.export(ident,'../../auth.json')
    def test_auth_failure_creates_no_job(self):
        with patch('idea_parallax.web.check_codex',return_value={'chatgpt_login':False,'message':'login required'}):
            with self.assertRaises(ValidationError):self.dash.start(task(mode='codex',consent=True))
        self.assertEqual(self.dash.history(),[])
    def test_stop_is_graceful_and_resume_uses_same_input(self):
        started=threading.Event()
        async def slow(self,kind,packet,schema,workspace):
            started.set();await asyncio.sleep(20)
            return demo_output(kind,packet),{}
        with patch.object(Provider,'complete',slow):
            ident=self.dash.start(task(concurrency=1));self.assertTrue(started.wait(2))
            with self.assertRaises(ValidationError):self.dash.start(task())
            snap=self.dash.snapshot(ident);self.assertTrue(any(s['status']=='running' for s in snap['stages']))
            self.dash.stop(ident);snap=wait_done(self.dash,ident)
        self.assertEqual(snap['status'],'interrupted')
        self.assertFalse((self.dash.directory(ident)/'run/.lock').exists())
        # Interrupted calls still consume a slot; no implicit budget increase.
        before=snap['calls'];self.dash.resume(ident);after=wait_done(self.dash,ident)
        self.assertGreater(after['calls'],before);self.assertLessEqual(after['calls'],after['max_calls'])
    def test_completed_budget_not_extended_on_resume(self):
        ident=self.dash.start(task());wait_done(self.dash,ident)
        with self.assertRaises(ValidationError):self.dash.resume(ident)
    def test_history_restart(self):
        ident=self.dash.start(task());wait_done(self.dash,ident)
        self.dash.close();self.dash=Dashboard(Path(self.temp.name)/'jobs')
        self.assertEqual(self.dash.snapshot(ident)['status'],'completed', self.dash.snapshot(ident))


class WebHTTP(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.dash=Dashboard(Path(self.temp.name)/'jobs')
        self.server=Server(self.dash,0);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.dash.close();self.temp.cleanup()
    def request(self,path='/',body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        h={'X-Parallax-Token':self.server.token};h.update(headers or {})
        if body is not None:h.setdefault('Content-Type','application/json')
        conn.request('GET' if body is None else 'POST',path,body=json.dumps(body).encode('utf-8') if body is not None else None,headers=h)
        response=conn.getresponse();result=(response.status,dict(response.getheaders()),response.read());conn.close();return result
    def test_static_has_csp_no_token(self):
        code,h,b=self.request();self.assertEqual(code,200);self.assertIn('Content-Security-Policy',h);self.assertNotIn(self.server.token.encode(),b)
    def test_assets_packaged(self):
        for path in ['/app.js','/style.css']:self.assertEqual(self.request(path)[0],200)
    def test_missing_token(self):self.assertEqual(self.request('/api/jobs',headers={'X-Parallax-Token':''})[0],403)
    def test_wrong_host(self):self.assertEqual(self.request('/api/jobs',headers={'Host':'evil.example'})[0],403)
    def test_cross_origin(self):self.assertEqual(self.request('/api/jobs',task(),{'Origin':'https://evil.example'})[0],403)
    def test_nonjson_post(self):self.assertEqual(self.request('/api/jobs',task(),{'Content-Type':'text/plain'})[0],400)
    def test_bad_export(self):self.assertEqual(self.request('/api/jobs/'+('0'*32)+'/export/auth.json')[0],404)
    def test_http_launch_and_download(self):
        code,_,body=self.request('/api/jobs',task());self.assertEqual(code,201)
        ident=json.loads(body)['id'];wait_done(self.dash,ident)
        code,_,body=self.request('/api/jobs/'+ident);self.assertEqual(code,200);self.assertEqual(len(json.loads(body)['candidates']),6)
        code,h,b=self.request('/api/jobs/'+ident+'/export/report.html');self.assertEqual(code,200);self.assertIn('attachment',h['Content-Disposition']);self.assertIn(b'SYNTHETIC DEMO',b)


class ConcurrentStorage(unittest.TestCase):
    def test_checkpoint_replace_waits_for_poll_reader(self):
        from idea_parallax.io_utils import write_json
        import os
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            write_json(path, {'state': 'old'})
            read_open = threading.Event()
            release_reader = threading.Event()
            write_started = threading.Event()
            replaced = threading.Event()
            failures = []
            observed = []
            read_text = Path.read_text
            replace = os.replace

            def held_read(target, *args, **kwargs):
                if target == path:
                    read_open.set()
                    if not release_reader.wait(3):
                        raise AssertionError('reader release timed out')
                return read_text(target, *args, **kwargs)

            def tracked_replace(*args, **kwargs):
                replaced.set()
                return replace(*args, **kwargs)

            def reader():
                try:
                    observed.append(load_json(path))
                except BaseException as exc:
                    failures.append(exc)

            def writer():
                write_started.set()
                try:
                    write_json(path, {'state': 'new'})
                except BaseException as exc:
                    failures.append(exc)

            with patch.object(Path, 'read_text', held_read), patch('idea_parallax.io_utils.os.replace', tracked_replace):
                r = threading.Thread(target=reader)
                w = threading.Thread(target=writer)
                r.start()
                try:
                    self.assertTrue(read_open.wait(2))
                    w.start()
                    self.assertTrue(write_started.wait(2))
                    self.assertFalse(replaced.wait(.1), 'replacement raced an active reader')
                finally:
                    release_reader.set()
                    r.join(3)
                    if w.ident is not None:
                        w.join(3)
                self.assertFalse(r.is_alive())
                self.assertFalse(w.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(observed, [{'state': 'old'}])
            self.assertEqual(load_json(path), {'state': 'new'})

    def test_replace_permission_failure_keeps_previous_checkpoint(self):
        from idea_parallax.io_utils import write_json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            write_json(path, {'state': 'old'})
            with patch('idea_parallax.io_utils.os.replace', side_effect=PermissionError('fixture')):
                with self.assertRaises(PermissionError):
                    write_json(path, {'state': 'new'})
            self.assertEqual(load_json(path), {'state': 'old'})
            self.assertEqual(list(Path(directory).glob('.write-*')), [])
