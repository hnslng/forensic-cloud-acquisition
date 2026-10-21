/* Authorization code never persists in URL history, logs or local storage. */
(async () => {
  const query = new URLSearchParams(location.search);
  history.replaceState(null, '', '/api/oauth/callback');
  const result = document.getElementById('result');
  try {
    const context = JSON.parse(sessionStorage.getItem('fca-oauth') || 'null');
    sessionStorage.removeItem('fca-oauth');
    if (!context || !query.get('code') || query.get('error')) throw new Error();
    const csrf = document.cookie.split('; ').find(v => v.startsWith('__Host-fca_csrf='))?.split('=')[1];
    const response = await fetch('/api/oauth/complete', {
      method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf || ''},
      body:JSON.stringify({...context,state:query.get('state'),code:query.get('code')})
    });
    if (!response.ok) throw new Error();
    sessionStorage.setItem('fca-return-case',context.case_id);
    location.replace('/');
  } catch {
    result.textContent='Anmeldung konnte nicht abgeschlossen werden. Bitte FCA erneut öffnen und das Konto verbinden.';
    const link=document.createElement('a'); link.href='/'; link.textContent='Zurück zu FCA'; result.append(link);
  }
})();
