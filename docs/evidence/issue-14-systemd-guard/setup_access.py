"""Create the issue-owned EC2 access stack, retaining exact commands and results."""
import datetime,json,os
from pathlib import Path
import subprocess,time
BASE=Path(__file__).resolve().parent
OUT=BASE/'access';OUT.mkdir(exist_ok=True)
network=json.loads((BASE/'network.json').read_text())
def aws(label,*args):
 argv=['aws',*args,'--region',network['region'],'--output','json']
 p=subprocess.run(argv,capture_output=True,text=True,timeout=60,env=os.environ|{'AWS_PAGER':'','AWS_MAX_ATTEMPTS':'1'})
 (OUT/(label+'.json')).write_text(json.dumps({'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n')
 assert p.returncode==0,(label,p.stderr)
 return json.loads(p.stdout or '{}')
assert not (OUT/'create-started.json').exists(),'Reconcile previous create before retrying'
identity=aws('identity','sts','get-caller-identity');assert identity['Account']==network['account']
vpc=aws('vpc','ec2','describe-vpcs','--vpc-ids',network['vpc'])['Vpcs'][0]
assert vpc['IsDefault'] and vpc['State']=='available'
s=aws('subnet','ec2','describe-subnets','--subnet-ids',network['subnet'])['Subnets'][0]
assert s['VpcId']==network['vpc'] and s['AvailabilityZone']==network['zone'] and s['State']=='available'
stacks=aws('stacks','cloudformation','list-stacks')['StackSummaries']
assert not any(s['StackName']==network['stack_name'] and s['StackStatus']!='DELETE_COMPLETE' for s in stacks),'Stack name is already occupied'
(OUT/'create-started.json').write_text(json.dumps({'name':network['stack_name'],'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})+'\n')
r=aws('create','cloudformation','create-stack','--stack-name',network['stack_name'],'--template-body','file://'+str(BASE/'stack-template.json'),'--capabilities','CAPABILITY_IAM','--tags','Key=SymphonyIssue,Value=14')
deadline=time.monotonic()+600
for i in range(60):
 observed=aws('observe-'+str(i),'cloudformation','describe-stacks','--stack-name',r['StackId'])
 status=observed['Stacks'][0]['StackStatus']
 if status=='CREATE_COMPLETE':
  (BASE/'stack-observed.json').write_text(json.dumps(observed,indent=2)+'\n');print(r['StackId'],status,flush=True);break
 assert status=='CREATE_IN_PROGRESS',status
 assert time.monotonic()<deadline
 time.sleep(10)
else:raise RuntimeError('Stack observation timeout; reconcile before retrying')
