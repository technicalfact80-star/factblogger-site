(function(){
  const menuButton=document.querySelector('[data-menu-button]');
  const nav=document.querySelector('[data-site-nav]');
  if(menuButton&&nav){menuButton.addEventListener('click',()=>{const open=nav.classList.toggle('is-open');menuButton.setAttribute('aria-expanded',String(open));});}
  const search=document.querySelector('[data-post-search]');
  const category=document.querySelector('[data-category-filter]');
  const language=document.querySelector('[data-language-filter]');
  const cards=[...document.querySelectorAll('[data-post-card]')];
  function filter(){
    const q=(search?.value||'').trim().toLocaleLowerCase();
    const c=category?.value||'all';
    const l=language?.value||'all';
    let count=0;
    cards.forEach(card=>{
      const hay=(card.dataset.search||'').toLocaleLowerCase();
      const matchesQ=!q||hay.includes(q);
      const matchesC=c==='all'||card.dataset.category===c;
      const matchesL=l==='all'||card.dataset.language===l;
      const show=matchesQ&&matchesC&&matchesL;
      card.hidden=!show;if(show)count++;
    });
    const empty=document.querySelector('[data-empty-state]');
    if(empty)empty.hidden=count>0;
    const result=document.querySelector('[data-result-count]');
    if(result)result.textContent=count+' article'+(count===1?'':'s');
  }
  [search,category,language].filter(Boolean).forEach(el=>el.addEventListener(el===search?'input':'change',filter));
})();
