"""Check direct filesystem autoload refusal, then verify policy after reboot."""
import base64,datetime,gzip,json,os
from pathlib import Path
import subprocess,time,uuid
BASE=Path(__file__).resolve().parent
CASE=BASE/'cases/aws-mantle-1-x86_64'
result=json.loads((CASE/'result.json').read_text());assert result['status']=='passed'
OUT=CASE/'followup';OUT.mkdir(exist_ok=True)
assert not (OUT/'reboot-started.json').exists(),'Reconcile prior reboot before retrying'
instance=result['instance'];os.environ['R10_INSTANCE']=instance;os.environ['R10_COMMAND_LOG']=str(OUT/'commands')
from transport import host,ssm,admin
config=json.loads((BASE/'release-config.json').read_text())
def save(n,v):(OUT/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
def policy(label):
 source=base64.b64encode(gzip.compress((BASE/'policy.py').read_bytes())).decode()
 remote='/.bottlerocket/rootfs/local/symphony-14-runtime/policy-'+uuid.uuid4().hex
 code=f'''import base64,contextlib,gzip,io,json,pathlib,sys
sys.argv=['policy.py',{config['build_id']!r}]
buffer=io.StringIO()
try:
 with contextlib.redirect_stdout(buffer):
  exec(gzip.decompress(base64.b64decode({source!r})))
except SystemExit:
 pass
p=pathlib.Path({remote!r});p.parent.mkdir(parents=True,exist_ok=True)
packed=gzip.compress(buffer.getvalue().encode());p.write_bytes(packed)
print(json.dumps({{'path':str(p),'size':len(packed)}}))
'''
 receipt=json.loads(ssm(label,admin(code),300));packed=bytearray()
 for offset in range(0,receipt['size'],6000):
  code='import base64,pathlib;p=pathlib.Path('+repr(receipt['path'])+');'+f'print(base64.b64encode(p.read_bytes()[{offset}:{offset+6000}]).decode())'
  packed.extend(base64.b64decode(ssm(label+'-read',admin(code)).strip()))
 assert len(packed)==receipt['size']
 report=json.loads(gzip.decompress(packed));save(label,report);assert report['status']=='passed',report['errors']
 return report
try:
 target='/local/symphony14-binfmt-probe'
 rc,out,err=host('mount-target-preflight',['test','!','-e',target]);assert rc==0,(out,err)
 rc,out,err=host('mount-target-create',['mkdir',target]);assert rc==0,(out,err)
 rc,out,err=host('direct-mount',['mount','-t','binfmt_misc','none',target])
 save('direct-mount',{'argv':['mount','-t','binfmt_misc','none',target],'exit_code':rc,'stdout':out,'stderr':err})
 assert rc!=0,'Direct binfmt mount unexpectedly succeeded'
 before=policy('policy-after-direct-mount');assert before['boot_id']==result['boot_id']
 rc,out,err=host('mount-target-remove',['rmdir',target]);assert rc==0,(out,err)
 save('reboot-started',{'instance':instance,'old_boot_id':before['boot_id'],'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 argv=['aws','ec2','reboot-instances','--instance-ids',instance,'--region','us-east-2','--output','json']
 p=subprocess.run(argv,capture_output=True,text=True,timeout=60,env=os.environ|{'AWS_MAX_ATTEMPTS':'1'})
 save('reboot-command',{'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==0
 time.sleep(45)
 # Read-only SSM probes may observe Online before reboot; boot ID is decisive.
 for i in range(40):
  argv=['aws','ssm','describe-instance-information','--filters','Key=InstanceIds,Values='+instance,'--region','us-east-2','--output','json']
  p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
  save('ssm-online-'+str(i),{'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==0
  rows=json.loads(p.stdout)['InstanceInformationList']
  if rows and rows[0]['PingStatus']=='Online':
   observed=ssm('reboot-readiness','if apiclient exec admin true >/dev/null 2>&1; then echo ADMIN_READY; else echo ADMIN_WAIT; fi')
   if observed.strip()=='ADMIN_READY':
    boot=ssm('reboot-boot-id',admin("import pathlib;print(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip())")).strip()
    if boot!=before['boot_id']:break
  time.sleep(15)
 else:raise RuntimeError('New boot was not observed; reconcile instance and SSM commands')
 after=policy('policy-after-reboot');assert after['boot_id']!=before['boot_id']
 save('result',{'status':'passed','instance':instance,'old_boot_id':before['boot_id'],'new_boot_id':after['boot_id'],'direct_mount_refused':True,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 print(instance,'direct mount refusal and reboot policy passed',flush=True)
except Exception as e:
 save('result',{'status':'failed','instance':instance,'error':repr(e)});raise
