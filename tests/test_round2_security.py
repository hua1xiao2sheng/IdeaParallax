import asyncio
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from idea_parallax.config import provider_config
from idea_parallax.engine import Engine
from idea_parallax.io_utils import ValidationError, write_text, load_json
from idea_parallax.providers import Provider, ProviderError, validate_endpoint, run_process, safe_env
from helpers import brief, config

class Security(unittest.TestCase):
    def test_remote_http_refused(self):
        with self.assertRaises(ValidationError): validate_endpoint('http://example.com/v1')
    def test_local_http_allowed(self):
        self.assertEqual(validate_endpoint('http://127.0.0.1:8000/v1/'), 'http://127.0.0.1:8000/v1')
    def test_credential_url_refused(self):
        with self.assertRaises(ValidationError): validate_endpoint('https://user:secret@example.com/v1')
    def test_query_secret_refused(self):
        with self.assertRaises(ValidationError): validate_endpoint('https://example.com/v1?key=secret')
    def test_environment_not_inherited_by_commands(self):
        with patch.dict(os.environ, {'IDEAPARALLAX_TEST_SECRET': 'not-for-child'}):
            self.assertNotIn('IDEAPARALLAX_TEST_SECRET', safe_env({}))
    def test_explicit_allowlist(self):
        with patch.dict(os.environ, {'TEST_ALLOWED': 'ok'}):
            self.assertEqual(safe_env({'env_allowlist':['TEST_ALLOWED']})['TEST_ALLOWED'], 'ok')
    def test_invalid_allowlist_fails_early(self):
        with self.assertRaises(ValidationError): provider_config({'type':'codex','env_allowlist':'ALL'})
    def test_direct_key_field_refused(self):
        with self.assertRaises(ValidationError): provider_config({'type':'api','api_key':'SECRET','model':'x'})
    def test_shell_string_refused(self):
        with self.assertRaises(ValidationError): provider_config({'type':'command','command':'echo x; rm file'})
    def test_symlink_parent_write_refused(self):
        if os.name == 'nt': self.skipTest('symlink privileges vary on Windows')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'real').mkdir(); (p/'alias').symlink_to(p/'real',target_is_directory=True)
            with self.assertRaises(ValidationError): write_text(p/'alias'/'new.txt','not allowed')

class AsyncSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_symlink_root_refused(self):
        if os.name == 'nt': self.skipTest('symlink privileges vary on Windows')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'real').mkdir(); (p/'alias').symlink_to(p/'real',target_is_directory=True)
            with self.assertRaises(ValidationError): await Engine(brief(),config(),p/'alias'/'run').run()
    async def test_no_command_execution_without_optin(self):
        with tempfile.TemporaryDirectory() as d:
            p=Provider(provider_config({'type':'command','command':[sys.executable,'-c','print("{}")']}))
            with self.assertRaises(ProviderError): await p.complete('generate',{}, {},Path(d))
    async def test_process_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ProviderError,'timed out'):
                await run_process([sys.executable,'-c','import time; time.sleep(30)'],'',Path(d),1,safe_env({}))
    async def test_process_output_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ProviderError,'size limit'):
                await run_process([sys.executable,'-c','print("x"*5000000)'],'',Path(d),5,safe_env({}))
    async def test_html_escapes_model_or_user_text(self):
        with tempfile.TemporaryDirectory() as d:
            b=brief(); b['topic']='<script>alert("x")</script><img src=x onerror=alert(1)>'
            root=Path(d)/'run'; await Engine(b,config(),root).run()
            html=(root/'report.html').read_text()
            self.assertNotIn('<script>alert(',html)
            self.assertNotIn('<img src=x',html)
            self.assertIn('&lt;script&gt;',html)
            self.assertIn('Content-Security-Policy',html)
    async def test_stderr_secrets_not_persisted(self):
        secret='test-secret-not-real-credential'
        with tempfile.TemporaryDirectory() as d:
            c=config(); c['branches']=c['branches'][:1]
            c['provider']={'type':'command','command':[sys.executable,'-c','import os,sys;sys.stderr.write(os.getenv("TEST_SECRET",""));sys.exit(3)'],'env_allowlist':['TEST_SECRET']}
            root=Path(d)/'run'
            with patch.dict(os.environ,{'TEST_SECRET':secret}):
                r=await Engine(brief(),c,root,allow_commands=True).run()
            self.assertEqual(r['status'],'failed')
            for f in root.rglob('*.json'):
                self.assertNotIn(secret,f.read_text())
