'use strict';
const API='https://api.github.com';
const REPO='/repos/belus6/jr-live-intel';
const WORKFLOW=REPO+'/actions/workflows/generate-outlook.yml';
const node=id=>document.getElementById(id);
let githubToken='',busy=false;
function message(text){node('status').textContent=text;}
async function github(path,options={}){
 const response=await fetch(API+path,{...options,headers:{Accept:'application/vnd.github+json',Authorization:'Bearer '+githubToken,'X-GitHub-Api-Version':'2022-11-28',...options.headers}});
 if(!response.ok){if(response.status===404)throw new Error('Workflow or report not found. The Outlook changes must be merged into main first.');if(response.status===401||response.status===403)throw new Error('GitHub access was denied. Check token expiration and repository permissions.');throw new Error('GitHub returned HTTP '+response.status+'. Check the workflow before trying a new generation.');}
 return response.status===204?null:response.json();
}
node('connect-form').addEventListener('submit',async event=>{
 event.preventDefault();const input=node('github-token');const candidate=input.value.trim();input.value='';
 if(!candidate.startsWith('github_pat_')){message('Enter a GitHub fine-grained token starting with github_pat_. Do not enter your OpenAI API key here.');return;}
 node('connect').disabled=true;githubToken=candidate;
 try{const user=await github('/user');if(user.login.toLowerCase()!=='belus6')throw new Error('Only the belus6 account can generate Outlook reports.');
 await github(WORKFLOW);node('connection').hidden=true;node('disconnect').hidden=false;node('generate').disabled=false;message('Connected as belus6. Ready to generate a fresh report.');
 }catch(error){githubToken='';message(error.message);}finally{node('connect').disabled=false;}
});
node('disconnect').addEventListener('click',()=>{githubToken='';node('connection').hidden=false;node('disconnect').hidden=true;node('generate').disabled=true;message('Disconnected.');});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
node('generate').addEventListener('click',async()=>{
 if(busy||!githubToken)return;
 busy=true;node('generate').disabled=true;node('disconnect').disabled=true;node('run-link').hidden=true;
 const requestId=crypto.randomUUID();let dispatched=false;
 try{
  message('Starting a new Outlook report…');
  await github(WORKFLOW+'/dispatches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ref:'main',inputs:{request_id:requestId}})});dispatched=true;
  message('Request accepted. Waiting for the research workflow…');
  let run=null;
  for(let attempt=0;attempt<120;attempt++){
   await pause(15000);
   if(!run){const result=await github(WORKFLOW+'/runs?event=workflow_dispatch&per_page=30');run=result.workflow_runs.find(item=>item.display_title==='Juniper Outlook '+requestId);}
   else run=await github(REPO+'/actions/runs/'+run.id);
   if(!run)continue;
   node('run-link').href='https://github.com/belus6/jr-live-intel/actions/runs/'+run.id;node('run-link').hidden=false;
   if(run.status==='completed'){
    if(run.conclusion!=='success')throw new Error('Generation ended with '+run.conclusion+'. Check the linked workflow. Partial API usage may have been billed.');
    const file=await github(REPO+'/contents/docs/data/outlook/generated/'+requestId+'.json?ref=main');
    const bytes=Uint8Array.from(atob(file.content.replace(/\s/g,'')),c=>c.charCodeAt(0));const edition=JSON.parse(new TextDecoder().decode(bytes));
    if(edition.id!==requestId||edition.status!=='draft')throw new Error('The completed report did not match this request.');
    // Only report content, never credentials, is retained to avoid a Pages deployment delay.
    sessionStorage.setItem('juniper-outlook-'+requestId,JSON.stringify(edition));
    const reportUrl='outlook.html?draft='+encodeURIComponent(requestId);
    node('report-frame').src=reportUrl;node('open-report').href=reportUrl;node('result').hidden=false;
    message('Your fresh Outlook is ready below. You can generate another report without reconnecting while this page stays open.');return;
   }
   message(run.status==='queued'?'Queued. Another feed update or report may be running.':'Researching sources and writing your Outlook. This can take several minutes…');
  }
  throw new Error('The workflow is still pending. Check GitHub progress before starting another report.');
 }catch(error){message(error.message+(dispatched?' Request ID: '+requestId:''));}
 finally{busy=false;node('generate').disabled=!githubToken;node('disconnect').disabled=false;}
});
