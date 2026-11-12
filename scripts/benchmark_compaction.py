#!/usr/bin/env python3
"""Paired end-to-end compaction recall benchmark using the local app-server."""
import argparse, concurrent.futures, json, os, queue, random, subprocess, threading, time
from pathlib import Path

QUESTIONS = {
    'release': 'Current release identifier',
    'old_release': 'Superseded release identifier',
    'owner': 'Current release owner',
    'window': 'Approved deployment window, including timezone',
    'rollback': 'Exact rollback trigger',
    'backup': 'Exact backup path',
    'command': 'Exact validation command',
    'retention': 'Required retention period',
    'migration_approved': 'Is the irreversible migration approved? Answer yes/no',
    'delete_approved': 'Is deleting source archives approved? Answer yes/no',
    'pending': 'Outstanding decision that needs user input',
    'max_workers': 'Maximum worker count',
    'min_free': 'Minimum free disk space before starting',
    'order': 'Required three-step execution order as a string separated by >',
    'exception': 'Exception to the retry rule',
    'unit': 'Unit used by the latency threshold',
    'unknown': 'Who approved the production firewall change? If absent answer unknown',
    'final_check': 'Final post-deployment check',
}

def fixture(seed):
    rng = random.Random(seed)
    expected = dict(release=f'iris-{seed}-b', old_release=f'iris-{seed}-a',
        owner='Mina', window='03:10-03:35 UTC', rollback='error rate > 0.7% for 4 minutes',
        backup=f'/srv/backups/iris-{seed}/preflight.snapshot',
        command=f'iris verify --seed {seed} --strict', retention='23 days',
        migration_approved='no', delete_approved='no', pending='choose west or north region',
        max_workers='7', min_free='18 GiB', order='snapshot>verify>switch',
        exception='never retry a partially committed payment', unit='milliseconds',
        unknown='unknown', final_check='compare invoice totals with the frozen ledger')
    facts = [f'Release handoff field {k}: {v}.' for k,v in expected.items()
             if k not in ('release','old_release','unknown')]
    rng.shuffle(facts)
    paragraphs = [f'Initial plan: release iris-{seed}-a. A migration was proposed but not authorized.']
    # Deterministic unrelated engineering notes put important details throughout a long context.
    for i in range(120):
        paragraphs.append(f'Workstream {i}: staging test batch {rng.randrange(10000)} covered cache eviction, '
                          f'pagination and retry ordering. The synthetic run used {rng.randrange(100,999)} '
                          'records. These observations describe experiments, not production requirements. '
                          'Keep the signed release handoff constraints authoritative over experimental logs.')
        if i % 7 == 3 and facts:
            paragraphs.append(facts.pop())
    paragraphs.extend(facts)
    paragraphs.append(f'FINAL CORRECTION: Current release is iris-{seed}-b, replacing iris-{seed}-a. '
                      'Mina is still the owner. Migration and archive deletion remain unapproved. '
                      'Do not treat proposed actions as permission.')
    # This later message exceeds the 64k recent-message retention budget, so
    # the scored facts in the first message must survive through the summary.
    tail=[]
    for i in range(1300):
        tail.append(f'Historical staging observation {i}: cache partition {rng.randrange(100000)} '
                    'completed a synthetic workload. The result is an unrelated archived measurement, '
                    'not a revision to the release handoff. It describes pagination, timestamp parsing, '
                    'queue fairness, reconnect timing, log rotation, retry backoff, and temporary object '
                    'cleanup. All release decisions, limits, approvals, and literal commands in the '
                    'earlier handoff remain authoritative. No additional production permission is granted.')
    return ['\n\n'.join(paragraphs), '\n\n'.join(tail)], expected

class Server:
    def __init__(self, binary, config, directory):
        self.directory=directory; directory.mkdir(parents=True,exist_ok=True)
        self.log=open(directory/'runtime.log','w')
        env=dict(os.environ, RUST_LOG='codex_m=info,feedback_tags=info')
        args=[binary,'app-server']
        for key,value in config.items(): args.extend(['-c',f'{key}={json.dumps(value)}'])
        self.p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                stderr=self.log,text=True,env=env)
        self.q=queue.Queue();self.n=0;self.events=[]
        def read():
            for line in self.p.stdout:
                try:self.q.put(json.loads(line))
                except json.JSONDecodeError: pass
            self.q.put({'eof':True})
        threading.Thread(target=read,daemon=True).start()
        self.call('initialize',{'clientInfo':{'name':'codex-m-recall-benchmark','version':'1'},
                               'capabilities':{'experimentalApi':True}})
        self.send({'method':'initialized'})
    def send(self,x): self.p.stdin.write(json.dumps(x)+'\n');self.p.stdin.flush()
    def next(self,deadline):
        x=self.q.get(timeout=max(0.1,deadline-time.monotonic()))
        self.events.append(x)
        with (self.directory/'events.jsonl').open('a') as event_log:event_log.write(json.dumps(x)+'\n')
        if x.get('eof'): raise RuntimeError('app-server exited')
        if 'method' in x and 'id' in x:
            self.send({'id':x['id'],'error':{'code':-32601,'message':'Benchmark does not allow interactive requests'}})
        return x
    def call(self,method,params,timeout=180):
        self.n+=1;rid=self.n;self.send({'id':rid,'method':method,'params':params})
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            x=self.next(deadline)
            if x.get('id')==rid:
                if 'error' in x: raise RuntimeError(x['error'])
                return x.get('result')
        raise TimeoutError(method)
    def until(self,method,timeout=300):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            x=self.next(deadline)
            if x.get('method')==method:return x['params']
            if method=='thread/compacted' and x.get('method')=='item/completed' and x.get('params',{}).get('item',{}).get('type')=='contextCompaction':return x['params']
        raise TimeoutError(method)
    def turn(self,tid,text):
        start=len(self.events)
        self.call('turn/start',{'threadId':tid,'input':[{'type':'text','text':text}]})
        done=self.until('turn/completed')
        if done.get('turn',{}).get('status')=='failed': raise RuntimeError(done)
        messages=[]
        for x in self.events[start:]:
            if x.get('method')=='item/completed':
                item=x['params']['item']
                if item.get('type')=='agentMessage': messages.append(item.get('text',''))
        return '\n'.join(messages)
    def close(self):
        (self.directory/'events.json').write_text(json.dumps(self.events,indent=2))
        self.p.terminate()
        try:self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:self.p.kill()
        self.log.close()

def trial(binary,out,seed,condition):
    cfg={'model':'gpt-6-astra','model_reasoning_effort':'medium','service_tier':'fast',
         'model_auto_compact_token_limit':1000000,'model_post_turn_compact_threshold_percent':0}
    if condition=='sol': cfg.update({'model_routing.compaction_model':'gpt-6.1-sol',
        'model_routing.compaction_service_tier':'ultrafast',
        'model_routing.compaction_reasoning_effort':'medium'})
    s=Server(binary,cfg,out/f'{seed}-{condition}')
    result={'seed':seed,'condition':condition}
    try:
        context,expected=fixture(seed)
        t=s.call('thread/start',{'cwd':'/repos','model':'gpt-6-astra','serviceTier':'priority',
            'approvalPolicy':'never','sandbox':'read-only','ephemeral':True})
        tid=t['thread']['id'];result['thread_id']=tid
        s.turn(tid,'Store this synthetic project handoff for a later recall test. Do not use tools. '
                   'Reply only STORED. All details may be needed.\n\n'+context[0])
        s.turn(tid,'Retain the earlier release handoff. Store this unrelated archive too; reply only STORED.\n\n'+context[1])
        if condition!='control':
            started=time.monotonic();s.call('thread/compact/start',{'threadId':tid})
            s.until('thread/compacted');result['compaction_seconds']=time.monotonic()-started
        answer=s.turn(tid,'Without tools, answer the handoff questions as a single JSON object of strings. '
                          'Use exact literals from the handoff; do not invent missing facts. Questions: '+json.dumps(QUESTIONS))
        (s.directory/'answer.txt').write_text(answer)
        a=answer.find('{');b=answer.rfind('}')
        actual=json.loads(answer[a:b+1])
        result['correct']={k:actual.get(k)==v for k,v in expected.items()}
        result['score']=sum(result['correct'].values());result['total']=len(expected)
        usage=[x['params']['tokenUsage']['last'] for x in s.events
               if x.get('method')=='thread/tokenUsage/updated']
        result['token_usage_last_requests']=usage
        result['mismatches']={k:{'expected':v,'actual':actual.get(k)} for k,v in expected.items() if actual.get(k)!=v}
    except Exception as e:result['error']=str(e)
    finally:s.close()
    (s.directory/'result.json').write_text(json.dumps(result,indent=2));return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--out',required=True)
    p.add_argument('--trials',type=int,default=3);a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    jobs=[(seed,condition) for seed in [11,29,47][:a.trials] for condition in ['control','astra','sol']]
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(trial,a.binary,out,*job) for job in jobs]
        for f in concurrent.futures.as_completed(futures):
            result=f.result();results.append(result);print(json.dumps(result),flush=True)
            (out/'results.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
