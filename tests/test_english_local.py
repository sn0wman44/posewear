"""Browser regression for static labels, dynamic overlays, metadata and language switching.

Run against the local app: python -m pytest tests/test_english_local.py -q
"""
from playwright.sync_api import sync_playwright

SCAN=r'''()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n,r=[];
while(n=w.nextNode()){if(!n.parentElement.closest('script,style,textarea')&&/[\u3400-\u9fff\u3040-\u30ff]/.test(n.nodeValue))r.push(n.nodeValue.trim());}
for(const e of document.querySelectorAll('[title],[aria-label],[placeholder],[alt]'))for(const a of ['title','aria-label','placeholder','alt']){const v=e.getAttribute(a);if(v&&/[\u3400-\u9fff\u3040-\u30ff]/.test(v))r.push(a+': '+v);}
return [...new Set(r)];}'''

def test_english_throughout_galleries_and_dialogs():
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='msedge',headless=True)
  page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
  page.on('pageerror',lambda error:errors.append(str(error)))
  page.add_init_script("localStorage.setItem('lang',JSON.stringify('en'))")
  page.goto('http://127.0.0.1:8766',wait_until='domcontentloaded');page.wait_for_function('()=>!!window.StudioLanguage')
  assert not page.evaluate(SCAN)
  for tab in ['pose','depth','costume','anime','portrait','expr','hair','dyn','scene','light','prop','furn','fav','recent','studio']:
   page.locator(f'.tabs [data-tab="{tab}"]').click();page.wait_for_timeout(200)
   assert not page.evaluate(SCAN),(tab,page.evaluate(SCAN))
   if tab in ['pose','depth','costume','anime','portrait','scene']:
    page.locator('#grid .card').first.click();page.wait_for_timeout(200)
    assert not page.evaluate(SCAN),(tab,'preview',page.evaluate(SCAN))
    assert page.locator('#share-reference').is_visible()
    page.keyboard.press('Escape');page.wait_for_timeout(350)
  page.locator('.tabs [data-tab="pose"]').click();page.wait_for_timeout(200)
  page.locator('#help').click();page.wait_for_timeout(100);assert not page.evaluate(SCAN)
  page.keyboard.press('Escape');page.wait_for_timeout(150)
  # Switching both ways restores the original interface without changing filter values.
  page.locator('[data-lang="zh"]').click();page.wait_for_timeout(200)
  assert page.locator('html').get_attribute('lang')=='zh-CN'
  assert page.evaluate(SCAN)
  page.locator('[data-lang="en"]').click();page.wait_for_timeout(200)
  assert not page.evaluate(SCAN)
  page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150)
  assert not page.evaluate(SCAN)
  page.screenshot(path='integration/english-mobile.png',full_page=False)
  page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path='integration/english-desktop.png',full_page=False)
  assert not errors,errors
  browser.close()

def test_english_defaults_and_studio_return_navigation():
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='msedge',headless=True)
  # The new default also migrates the legacy Posewear Chinese preference once.
  for route in ['/','/video-studio','/library']:
   context=browser.new_context();page=context.new_page()
   page.add_init_script("localStorage.setItem('lang',JSON.stringify('zh'))")
   page.goto('http://127.0.0.1:8766'+route,wait_until='domcontentloaded')
   page.wait_for_function('()=>!!window.StudioLanguage')
   assert page.locator('html').get_attribute('lang')=='en'
   assert page.evaluate("JSON.parse(localStorage.getItem('lang'))")=='en'
   context.close()
  page=browser.new_page(viewport={'width':390,'height':844})
  page.goto('http://127.0.0.1:8766/video-studio',wait_until='domcontentloaded')
  back=page.locator('.studio-links a[href="/"]');assert back.is_visible()
  assert 'Product Video Studio' in back.inner_text()
  back.click();page.wait_for_url('http://127.0.0.1:8766/')
  assert page.locator('html').get_attribute('lang')=='en'
  browser.close()
