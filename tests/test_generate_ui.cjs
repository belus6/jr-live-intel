// Offline checks for authorization, dispatch correlation and duplicate-click protection.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=require('path');
class Node{constructor(){this.value='';this.hidden=false;this.disabled=false;this.textContent='';this.handlers={}}addEventListener(event,fn){this.handlers[event]=fn}}
async function harness(login='belus6',conclusion='success'){
 const ids=['github-token','connect','connect-form','connection','disconnect','generate','status','run-link','report-frame','open-report','result'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new Node()]));nodes['github-token'].value='github_pat_test_only';
 const calls=[],storage={},location={href:''};const edition={id:'test-request',status:'draft'};
 const fetch=async(url,options)=>{calls.push({url,options});let body;
 if(url.endsWith('/user'))body={login};
 else if(url.endsWith('/dispatches'))return{ok:true,status:204};
 else if(url.includes('/runs?'))body={workflow_runs:[{id:123,display_title:'Juniper Outlook test-request',status:'in_progress'}]};
 else if(url.endsWith('/actions/runs/123'))body={id:123,status:'completed',conclusion};
 else if(url.includes('/contents/'))body={content:Buffer.from(JSON.stringify(edition)).toString('base64')};
 else body={id:456};return{ok:true,status:200,json:async()=>body};};
 const context={document:{getElementById:id=>nodes[id]},fetch,crypto:{randomUUID:()=> 'test-request'},setTimeout:fn=>{queueMicrotask(fn)},sessionStorage:{setItem:(key,value)=>{storage[key]=value}},location,atob,Uint8Array,TextDecoder};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../docs/generate.js'),'utf8'),context);
 await nodes['connect-form'].handlers.submit({preventDefault(){}});
 return{nodes,calls,storage,location};
}
(async()=>{
 let h=await harness('another-account');assert(h.nodes.status.textContent.includes('Only the belus6'));assert(!h.calls.some(c=>c.url.endsWith('/dispatches')));assert.equal(h.nodes['github-token'].value,'');
 h=await harness();assert.equal(h.nodes.generate.disabled,false);const first=h.nodes.generate.handlers.click();const repeated=h.nodes.generate.handlers.click();await Promise.all([first,repeated]);
 const dispatch=h.calls.filter(c=>c.url.endsWith('/dispatches'));assert.equal(dispatch.length,1);assert.equal(JSON.parse(dispatch[0].options.body).inputs.request_id,'test-request');assert(h.nodes['report-frame'].src.includes('?draft=test-request'));assert.deepEqual(Object.keys(h.storage),['juniper-outlook-test-request']);assert(!JSON.stringify(h.storage).includes('github_pat_'));
 h=await harness('belus6','failure');await h.nodes.generate.handlers.click();assert(h.nodes.status.textContent.includes('Generation ended with failure'));assert.equal(h.location.href,'');assert.equal(h.calls.filter(c=>c.url.endsWith('/dispatches')).length,1);
 h=await harness();h.nodes.disconnect.handlers.click();assert(h.nodes.generate.disabled);assert(h.nodes.status.textContent.includes('Disconnected'));
 console.log('Generation UI checks passed: owner auth, one dispatch per click, matching result, no stored credential, failure handling, disconnect.');
})();
