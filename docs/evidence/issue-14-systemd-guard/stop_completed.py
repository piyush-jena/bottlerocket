"""Terminate only this round's three completed non-GPU validation instances."""
import json,os,subprocess,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
OUT=BASE/'partial-cleanup';OUT.mkdir(exist_ok=True)
def aws(label,*args):
 a=['aws',*args,'--region','us-east-2','--output','json'];p=subprocess.run(a,capture_output=True,text=True,timeout=60,env=os.environ|{'AWS_MAX_ATTEMPTS':'1'})
 (OUT/(label+'.json')).write_text(json.dumps({'argv':a,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n');assert p.returncode==0,(label,p.stderr);return json.loads(p.stdout or '{}')
ids=[];jobs={}
for name in ['aws-mantle-1-x86_64','aws-mantle-1-aarch64','aws-mantle-1-fips-x86_64']:
 result=json.loads((BASE/'cases'/name/'result.json').read_text());assert result['status']=='passed'
 ids.append(result['instance']);jobs[result['instance']]=result['case']['job']
assert json.loads((BASE/'cases/aws-mantle-1-x86_64/followup/result.json').read_text())['status']=='passed'
instances=[i for r in aws('before','ec2','describe-instances','--instance-ids',*ids)['Reservations'] for i in r['Instances']]
assert {i['InstanceId'] for i in instances}==set(ids)
volumes=[]
for i in instances:
 tags={t['Key']:t['Value'] for t in i['Tags']};assert tags['SymphonyIssue']=='14' and tags['SymphonyBuild']==jobs[i['InstanceId']]
 for m in i['BlockDeviceMappings']:
  if 'Ebs' in m:
   assert m['Ebs']['DeleteOnTermination'];volumes.append(m['Ebs']['VolumeId'])
aws('terminate','ec2','terminate-instances','--instance-ids',*ids)
for attempt in range(40):
 instances=[i for r in aws('after-'+str(attempt),'ec2','describe-instances','--instance-ids',*ids)['Reservations'] for i in r['Instances']]
 if all(i['State']['Name']=='terminated' for i in instances):break
 time.sleep(10)
else:raise RuntimeError('Termination not yet confirmed; retain IDs and reconcile')
remaining=aws('volumes-after','ec2','describe-volumes','--filters','Name=volume-id,Values='+','.join(volumes))['Volumes']
assert not remaining,remaining
result={'status':'passed','terminated_instances':ids,'deleted_instance_volumes':volumes,'retained':'Five private AMIs and their ten snapshots, access stack and local kit registry retained for GPU validation after capacity recovers.'}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
