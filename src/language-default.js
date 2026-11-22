// Start the unified app in English, including browsers with a legacy Posewear preference.
(() => {
 try {
  if(localStorage.getItem('studio-language-default')!=='en-v1'){
   localStorage.setItem('lang',JSON.stringify('en'));
   localStorage.setItem('studio-language-default','en-v1');
  }
  if(!localStorage.getItem('lang'))localStorage.setItem('lang',JSON.stringify('en'));
  if(!localStorage.getItem('tl'))localStorage.setItem('tl',JSON.stringify('en'));
  document.documentElement.lang=JSON.parse(localStorage.getItem('lang'))==='zh'?'zh-CN':'en';
  document.documentElement.dataset.lang=JSON.parse(localStorage.getItem('lang'));
 } catch {document.documentElement.lang='en';document.documentElement.dataset.lang='en';}
})();
