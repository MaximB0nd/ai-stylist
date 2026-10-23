const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.PLAYWRIGHT_CHANNEL || "msedge"});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const base = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:15091';
    const albumId = '11111111-1111-4111-8111-111111111111';
    const jobId = '22222222-2222-4222-8222-222222222222';
    let polls = 0, posts = 0, feedback = 0;
    await page.route('**/api/v1/**', async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      const send = (data, status=200) => route.fulfill({status, contentType:'application/json', body:JSON.stringify(data)});
      if (path === '/api/v1/auth/login') return send({access_token:'browser-test-token',token_type:'bearer',id:albumId});
      if (path === '/api/v1/auth/me') return send({id:albumId,name:'Test User',email:'test@example.com',created_at:'2026-10-20T10:00:00Z'});
      if (path === '/api/v1/albums') return send({album_ids:[albumId],total:1});
      if (path === `/api/v1/albums/${albumId}`) return send({id:albumId,title:'API album',created_at:'2026-10-20T10:00:00Z',photos:Array.from({length:5}, (_,i)=>({id:String(i),order_index:i,url:base+'/images/album/look01.png'}))});
      if (path === '/api/v1/generations') {
        posts++;
        const body = request.postDataBuffer().toString();
        for (const field of ['face_photo','body_photo','situation','styles','shoes','impressions']) assert.ok(body.includes(`name="${field}"`),field);
        assert.ok(body.includes('name="gender"\r\n\r\nf'));
        return send({generation_id:jobId,status:'QUEUED'},202);
      }
      if (path === `/api/v1/generations/${jobId}/status`) {
        polls++;
        return send(polls === 1 ? {status:'PROCESSING'} : {status:'COMPLETED',album_id:albumId});
      }
      if (path === '/api/v1/feedback') {
        feedback++;
        assert.deepEqual(request.postDataJSON(), {name:'Tester',email:'reply@example.com',comment:'Browser feedback'});
        if (feedback === 1) return send({detail:'Temporary failure'},503);
        return send({id:albumId},201);
      }
      return send({detail:'Unexpected request '+path},404);
    });
    await page.goto(base+'/gallery');
    await page.locator('[data-albums-status]').filter({hasText:'Войдите'}).waitFor();
    await page.locator('#authTrigger').click();
    await page.locator('#loginEmail').fill('test@example.com');
    await page.locator('#loginPassword').fill('Password123!');
    await page.locator('#authSubmit').click();
    await page.locator('.album-card').waitFor();
    assert.equal(await page.locator('.album-name').textContent(),'API album');
    await page.locator('.album-card').click();
    await page.locator('.look-card').first().waitFor();
    assert.equal(await page.locator('.look-card').count(),5);
    await page.locator('.look-card').first().click();
    await page.locator('dialog[open]').waitFor();
    await page.keyboard.press('ArrowRight');
    assert.ok((await page.locator('[data-lightbox-caption]').textContent()).includes('2 / 5'));
    await page.keyboard.press('Escape');
    await page.goto(base+'/');
    await page.locator('#home-albums .album-card').waitFor();
    assert.equal(await page.locator('#home-albums .album-name').textContent(), 'API album');
    await page.goto(base+'/feedback');
    await page.locator('.feedback-form [name=name]').fill('Tester');
    await page.locator('.feedback-form [name=email]').fill('reply@example.com');
    await page.locator('.feedback-form [name=message]').fill('Browser feedback');
    await page.locator('.feedback-submit').click();
    await page.locator('[data-feedback-status]').filter({hasText:'Temporary failure'}).waitFor();
    assert.equal(await page.locator('[name=message]').inputValue(),'Browser feedback');
    await page.locator('.feedback-submit').click();
    await page.locator('[data-feedback-status]').filter({hasText:'сохранён'}).waitFor();
    assert.equal(await page.locator('[name=message]').inputValue(),'');
    await page.goto(base+'/generation');
    await page.locator('#generation-form[data-ready=true]').waitFor();
    await page.locator('[name=age]').fill('25');
    await page.locator('[name=height]').fill('175');
    for (const [name,value] of Object.entries({gender:'female',occasion:'office',style:'casual',shoe:'loafers',mood:'confident'})) {
      await page.locator(`[name=${name}][value=${value}]`).check();
    }
    const photo = {name:'test.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=','base64')};
    for (const name of ['face','body']) await page.locator(`input[name=${name}]`).setInputFiles(photo);
    await page.waitForFunction(() => [...document.querySelectorAll('[data-photo]')].every(node => node.getAttribute('aria-busy') === 'false' && !node.querySelector('.generation-preview').hidden));
    await page.locator('.generation-generate').click();
    await page.waitForURL('**/generation?generation_id=*');
    await page.reload();
    await page.waitForURL('**/album/'+albumId, {timeout:15000});
    assert.equal(posts,1);
    await page.locator('.look-card').first().waitFor();
    await page.goto(base+'/profile');
    await page.locator('[data-profile-name]').filter({hasText:'Test User'}).waitFor();
    await page.locator('[data-logout]').click();
    assert.equal(await page.evaluate(()=>localStorage.getItem('aiStylistAuth')),null);
    assert.deepEqual(errors,[]);
    console.log('PASS: browser login, personal gallery, SPA album navigation, five photos, lightbox, feedback failure/retry, real multipart generation, refresh without duplicate POST, polling, profile and logout');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });

