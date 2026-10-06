'use strict';
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.hash.slice(1));
let token = params.get('token') || sessionStorage.getItem('parallax-session') || '';
if (token) sessionStorage.setItem('parallax-session', token);
if (params.has('token')) history.replaceState(null, '', location.pathname);
let selected = null, authenticated = false, lastSignature = '', busy = false, latest = null;
const names = {pending:'等待',queued:'排队中',starting:'准备中',running:'运行中',retrying:'重试中',succeeded:'已完成',completed:'已完成',failed:'失败',partial:'部分完成',interrupted:'已中断',stopping:'正在停止'};
function node(tag, content='', cls='') { const n=document.createElement(tag); n.textContent=content; if(cls)n.className=cls; return n; }
function showError(msg){$('error').textContent=msg;$('error').hidden=!msg;}
async function api(path, body, binary=false){
  const options={headers:{'X-Parallax-Token':token}};
  if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const response=await fetch(path,options);
  if(!response.ok){let e;try{e=await response.json();}catch{e={error:'服务未响应，请检查终端。'};}throw Error(e.error||'请求失败');}
  return binary?response.blob():response.json();
}
function updateEstimate(){
  const count=document.querySelectorAll('#strategies input:checked').length;
  const calls=count+($('review').checked?2:0);
  $('estimate').textContent=`已选 ${count} 条策略 · 无重试时最多 ${calls} 次外层调用。IdeaSpark 每次最多 1 个候选。`;
  $('start').disabled=!authenticated||!count||busy;
}
async function info(){
  $('recheck').disabled=true;
  try{
    const data=await api('/api/info');authenticated=data.codex.chatgpt_login;
    $('authStatus').textContent=authenticated?'已连接 · ChatGPT 登录':data.codex.installed?'CLI 已安装 · 登录待确认':'尚未找到 Codex CLI';
    $('authMessage').textContent=data.codex.message;
    if(!$('strategies').children.length){
      for(const [key, entry] of Object.entries(data.catalog)){
        const label=node('label','','strategy'),input=document.createElement('input');input.type='checkbox';input.value=key;input.checked=true;input.addEventListener('change',updateEstimate);
        label.append(input,node('span',entry.name));$('strategies').append(label);
      }
    }
    updateEstimate();
  }catch(e){showError(e.message);}finally{$('recheck').disabled=false;}
}
function collect(mode){
  let topic=$('topic').value.trim();if(!topic&&mode==='demo')topic='离线演示：RAG 如何寻找缺失证据';
  if(!topic)throw Error('请先填写研究内容。');
  let seeds=[];try{seeds=$('seeds').value.trim()?JSON.parse($('seeds').value):[];}catch{throw Error('种子论文 JSON 格式不正确。');}
  return {mode,brief:{topic,context:$('context').value,language:'zh-CN',constraints:$('constraints').value.split('\n').map(s=>s.trim()).filter(Boolean),seed_papers:seeds},
    strategies:[...document.querySelectorAll('#strategies input:checked')].map(n=>n.value),
    concurrency:Number($('concurrency').value),max_ideas:Number($('maxIdeas').value),model:$('model').value.trim(),
    review:$('review').checked,retrieval:$('retrieval').checked?'crossref':'none',consent:$('consent').checked};
}
async function start(mode){
  if(busy)return;showError('');
  try{const task=collect(mode);busy=true;updateEstimate();$('demo').disabled=true;
    const result=await api('/api/jobs',task);selected=result.id;lastSignature='';await refresh();
    $('runPanel').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){showError(e.message);}finally{busy=false;$('demo').disabled=false;updateEstimate();}
}
function field(parent, title, value){parent.append(node('h4',title),node('p',value||'未提供'));}
function detail(parent, title, id){const d=document.createElement('details');d.dataset.key=id;d.append(node('summary',title));parent.append(d);return d;}
function renderIdeas(candidates){
  const opened=new Set([...document.querySelectorAll('#candidates details[open]')].map(d=>d.dataset.key));
  const oldSource=$('sourceFilter').value;const sources=[...new Set(candidates.map(c=>c.source))];
  $('sourceFilter').replaceChildren(new Option('全部策略',''),...sources.map(s=>new Option(s,s)));$('sourceFilter').value=sources.includes(oldSource)?oldSource:'';
  $('candidates').replaceChildren();
  if(!candidates.length){$('candidates').append(node('p','尚无有效候选。分支返回后会显示在这里；失败时不会用演示数据替代。','hint'));}
  for(const idea of candidates){
    const card=node('article','','idea');card.dataset.source=idea.source;
    const tags=node('div','','tags');tags.append(node('span',idea.source,'tag'),node('span',idea.contribution_type,'tag'),node('span','策略移植 · 待验证','tag'));
    card.append(tags,node('h3',idea.title));field(card,'核心假说',idea.hypothesis);field(card,'技术机制',idea.mechanism);field(card,'拟议差异 · 尚待查新',idea.claimed_difference);
    const exp=detail(card,'最小实验与证伪计划',idea.id+'-exp');
    const labels={dataset:'数据集',baseline:'对照基线',metric:'评价指标',procedure:'实施步骤',falsification:'什么结果会反驳假说'};
    for(const [k,label] of Object.entries(labels))field(exp,label,idea.experiment[k]);
    field(exp,'资源需求',idea.compute_requirement);field(exp,'风险',idea.risks.join('\n'));field(exp,'建议查新检索式',idea.search_queries.join('\n'));
    const reviews=detail(card,'查看评审与下一步',idea.id+'-review');
    if(!idea.reviews.length)reviews.append(node('p','评审尚未完成或未启用。'));
    for(const r of idea.reviews){field(reviews,r.role==='scientific'?'科研价值评审':'可行性评审',`${r.novelty} / ${r.feasibility} / ${r.priority}`);field(reviews,'支持理由',r.strengths.join('\n'));field(reviews,'反方意见',r.objections.join('\n'));field(reviews,'下一步核实',r.next_checks.join('\n'));}
    for(const d of card.querySelectorAll('details'))d.open=opened.has(d.dataset.key);
    $('candidates').append(card);
  }
  filter();
}
function filter(){
  const q=$('filter').value.toLocaleLowerCase(), source=$('sourceFilter').value;let count=0;
  for(const card of document.querySelectorAll('.idea')){card.hidden=!(card.textContent.toLocaleLowerCase().includes(q)&&(!source||card.dataset.source===source));if(!card.hidden)count++;}
  $('visibleCount').textContent=`${count} 个`;
}
function render(data){
  latest=data;$('empty').hidden=true;$('runPanel').hidden=false;
  $('runTopic').textContent=data.topic;$('runState').textContent=names[data.status]||data.status;
  $('runMode').textContent=data.mode==='demo'?'SYNTHETIC DEMO · 合成演示':'真实 Codex · 研究提案';
  $('runMeta').textContent=`${new Date(data.created_at).toLocaleString()} · 并发 ${data.concurrency} · 任务 ${data.id.slice(0,8)}`;
  $('candidateCount').textContent=data.candidates.length;$('callCount').textContent=`${data.calls} / ${data.max_calls}`;
  $('runWarning').textContent=(data.error?data.error+' ':'')+(data.mode==='demo'?'这是合成测试数据，未调用真实模型。':'研究内容会通过本机 Codex 发给 OpenAI；没有自动运行实验。')+' '+(data.retrieval==='crossref'?`元数据检索：${data.retrieval_status}；不是全文查新。`:'未启用文献检索；建议提供论文原文片段。');
  $('stop').hidden=!data.active;$('stop').disabled=data.status==='stopping';$('resume').hidden=!data.can_resume;$('exports').hidden=!data.report_ready;
  $('stages').replaceChildren();
  for(const s of data.stages){const card=node('div','','stage'),head=node('div','','stage-head');head.append(node('strong',s.label),node('span',names[s.status]||s.status,'status '+s.status));card.append(head);if(s.error)card.append(node('p',s.error));$('stages').append(card);}
  renderIdeas(data.candidates);
}
async function refresh(){
  try{
    const jobs=await api('/api/jobs');$('history').replaceChildren();
    if(!selected&&jobs.length)selected=jobs[0].id;
    if(!jobs.length)$('history').append(node('p','还没有任务。','hint'));
    for(const j of jobs){const b=node('button',j.topic.slice(0,70),j.id===selected?'selected':'');b.append(node('small',`${j.mode==='demo'?'演示':'Codex'} · ${names[j.status]||j.status} · ${new Date(j.created_at).toLocaleString()}`));b.onclick=()=>{selected=j.id;lastSignature='';refresh();};$('history').append(b);}
    if(selected){const data=await api('/api/jobs/'+selected),signature=JSON.stringify(data);if(signature!==lastSignature){render(data);lastSignature=signature;}}
  }catch(e){showError(e.message);}
}
async function action(name){if(!selected)return;showError('');try{await api(`/api/jobs/${selected}/${name}`,{});lastSignature='';await refresh();}catch(e){showError(e.message);}}
$('taskForm').addEventListener('submit',e=>{e.preventDefault();start('codex');});$('demo').onclick=()=>start('demo');$('recheck').onclick=()=>{showError('');info();};$('stop').onclick=()=>action('stop');$('resume').onclick=()=>action('resume');$('review').onchange=updateEstimate;
$('filter').oninput=filter;$('sourceFilter').onchange=filter;
$('notesFile').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{if(f.size>100000||!(/\.(txt|md)$/i.test(f.name)))throw Error('仅支持 100KB 以内的 .txt / .md 笔记，不支持 PDF。');const content=await f.text();const combined=$('context').value+'\n'+content;if(combined.length>30000)throw Error('背景材料最多 30000 字符，请选取关键片段。');$('context').value=combined.trim();}catch(err){showError(err.message);}e.target.value='';};
for(const button of document.querySelectorAll('[data-export]'))button.onclick=async()=>{try{const name=button.dataset.export,blob=await api(`/api/jobs/${selected}/export/${name}`,undefined,true);const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='IdeaParallax-'+selected.slice(0,8)+'-'+name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}catch(e){showError(e.message);}};
(async()=>{await info();await refresh();const tick=async()=>{await refresh();setTimeout(tick,2000);};setTimeout(tick,2000);})();
