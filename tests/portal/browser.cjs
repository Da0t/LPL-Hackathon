/* Opt-in live smoke: provision demo users and start both servers first.
 * Uses real Cognito/DynamoDB/Bedrock; creates one synthetic review request.
 * NODE_PATH=/path/to/playwright/node_modules node tests/portal/browser.cjs
 */
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const base = process.env.PORTAL_URL || 'http://127.0.0.1:3200';
const users = JSON.parse(fs.readFileSync(process.env.PORTAL_ACCESS_FILE || 'var/demo-access.json'));
(async () => {
 const browser = await chromium.launch({headless:true});
 try {
  let submitted;
  for (const [email, user] of Object.entries(users)) {
   const context = await browser.newContext({viewport:{width:1600,height:1100}});
   const page = await context.newPage();
   const errors=[]; page.on('pageerror', e=>errors.push(e.message));
   await page.goto(base+'/login');
   await page.getByLabel('Email address').fill(email);
   await page.getByLabel('Password', {exact:true}).fill(user.password);
   await page.getByRole('button',{name:'Sign in',exact:true}).click();
   await page.waitForURL('**/'+(user.role==='staff'?'dashboard':'workspace'),{timeout:30000});
   if (user.role==='staff') {
    const cases=await (await context.request.get(base+'/api/staff/cases')).json();
    assert(cases.cases.some(c=>c.case_id===submitted));
    const detail = await context.request.get(base+"/api/staff/cases/"+submitted);
    assert.equal(detail.status(),200);
    assert.equal((await detail.json()).case_id,submitted);
   } else {
    const profile = await (await context.request.get(base+'/api/portal/me')).json();
    assert.equal(profile.client_id,user.client_id);
    assert(profile.accounts.length>=4 && profile.activity.length>=30);
    assert.equal((await context.request.get(base+'/api/staff/cases',{headers:{'X-Demo-Role':'staff'}})).status(),403);
    if (user.client_id==='CLIENT-017') {
     await page.goto(base+'/workspace/profile');
     const name=page.getByLabel('Preferred name',{exact:true});await name.waitFor();
     const before=await name.inputValue();
     await name.fill(before+' Test');
     await page.getByRole('button',{name:'Save profile',exact:true}).first().click();
     await page.getByText('Your profile was saved.',{exact:true}).waitFor();
     await page.reload();await name.waitFor();assert.equal(await name.inputValue(),before+' Test');
     await name.fill(before);await page.getByRole('button',{name:'Save profile',exact:true}).first().click();
     await page.getByText('Your profile was saved.',{exact:true}).waitFor();
     await page.goto(base+'/workspace/requests/new');
     await page.getByLabel('Your request',{exact:true}).fill('I want to discuss withdrawing $6,000 from my old workplace retirement account for home repairs.');
     await page.getByRole('button',{name:'Confirm and send request',exact:true}).waitFor();
     await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Confirm and send request'));return b&&!b.disabled},{timeout:120000});
     await page.getByLabel('Account to discuss',{exact:true}).selectOption('ACCT-201');
     await page.getByLabel('Amount to discuss (USD, optional)',{exact:true}).fill('6000');
     await page.getByLabel('Request description',{exact:true}).fill('Please discuss a possible $6,000 withdrawal from my old workplace rollover IRA for home repairs. I want an advisor to explain the implications before deciding.');
     console.log('Request ready');await page.screenshot({path:'/tmp/coherent-request-filled.png',fullPage:true});
     const archive=page.waitForResponse(r=>r.url().endsWith('/archive')&&r.request().method()==='POST',{timeout:120000});
     await page.getByRole('button',{name:'Confirm and send request',exact:true}).click();
     const response=await archive;assert.equal(response.status(),200);const doc=await response.json();submitted=doc.case_id;
     assert.equal(doc.account.account_id,'ACCT-201');assert.equal(doc.account.balance,84000);assert.equal(doc.amount_requested,6000);assert(doc.history.length>=10);
     assert(doc.history.every(e=>e.account_id==='ACCT-201'));assert(!JSON.stringify(doc).includes('ssn'));
     await page.getByRole('button',{name:'Request sent',exact:true}).waitFor();
     await page.pdf({path:'/tmp/coherent-request-print.pdf',format:'A4',printBackground:true,preferCSSPageSize:true});
     await page.goto(base+'/workspace/requests');
     await page.getByText(doc.request_description,{exact:true}).first().waitFor();
     await page.goto(base+'/workspace/requests/new');
     await page.getByLabel('Pause automatic suggestions',{exact:true}).click();
     await page.getByLabel('Your request',{exact:true}).fill('A draft that should stay local after refresh.');
     let posts=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/intake'))posts++});
     await page.reload();await page.getByText(/Draft restored/).waitFor();
     await page.waitForTimeout(1800);assert.equal(posts,0);
     await page.setViewportSize({width:390,height:844});
     for(const route of ['/workspace','/workspace/profile','/workspace/finances','/workspace/requests/new']) {
      await page.goto(base+route);await page.locator('h1').waitFor();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'mobile overflow: '+route);
     }
     await page.screenshot({path:'/tmp/coherent-mobile.png',fullPage:true});
    }
   }
   assert.deepEqual(errors,[]);
   await context.request.post(base+'/api/auth/logout');
   assert.equal((await context.request.get(base+'/api/portal/me')).status(),401);
   await context.close();console.log('PASS',user.role,user.client_id||'staff');
  }
  console.log('PASS live portal workflow, cloud document, saved profile, mobile layouts and isolation');
 } catch (error) {
  for (const c of browser.contexts()) for (const p of c.pages()) await p.screenshot({path:'/tmp/coherent-test-failure.png',fullPage:true}).catch(()=>{});
  throw error;
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
