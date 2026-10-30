// The relay console: the owner writes to a team (or lets the relay agent route it), the server puts the message in the
// relay outbox (POST /api/relay, guarded: the page's own token, same origin, loopback), and the `relay` projection
// brings back each message's state (queued, claimed, delivered, failed) and the teams' replies. Approvals never go
// this way (ADR 005 decision 5): the agent refuses them and says so.
// Loaded after index.html's script: it shares its globals (base, live, sum, esc, SECTIONS).
(() => {
  const el = id => document.getElementById(id);
  let token = null, about = null, sending = false;
  fetch(new URL('api/relay/token', base)).then(r => r.ok ? r.json() : Promise.reject()).then(d => { token = d.token; renderRelay(); })
    .catch(() => { token = null; renderRelay(); });
  const ago = s => s < 90 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`;
  const CHIP = {queued: 'wait', claimed: 'wait', delivered: 'ok', failed: 'bad'};

  function renderRelay() {
    const r = sum('relay'), sel = el('relay-to');
    if (!sel) return;
    const now = Date.now() / 1000;
    el('relay-agent').innerHTML = !token ? 'Messages need the cstack server (this is a snapshot).'
      : r.agent_online ? `<i class="dot fresh"></i>Relay agent online · seen ${ago(now - r.agent_seen)} ago`
      : `<i class="dot"></i>Relay agent ${r.agent_seen ? 'last seen ' + ago(now - r.agent_seen) + ' ago' : 'not started'}: messages wait in the outbox`;
    const want = sel.value;
    const teams = (r.teams || []).map(t => `<option value="${esc(t.id || t.name)}">${esc(t.name)}${t.state ? ' · ' + esc(t.state) : ''}</option>`).join('');
    const html = `<option value="auto">Orchestrator decides</option>${teams}`;
    if (sel.dataset.html !== html) { sel.innerHTML = html; sel.dataset.html = html; sel.value = [...sel.options].some(o => o.value === want) ? want : 'auto'; }
    el('relay-send').disabled = !token || sending;
    el('relay-about').hidden = !about;
    el('relay-about').innerHTML = about ? `About: ${esc(about)} <button type="button" aria-label="Clear the topic">×</button>` : '';
    el('relay-thread').innerHTML = (r.messages || []).slice(0, 6).map(m => `<div class="msg">
      <div class="mh"><span class="chip ${CHIP[m.state] || 'wait'}">${m.state}</span><span>${esc(m.to_name || (m.to === 'auto' ? 'orchestrator decides' : m.to))}</span><span class="age">${ago(now - m.at)}</span></div>
      <p>${esc(m.text)}</p>${m.note ? `<p class="note">${esc(m.note)}</p>` : ''}
      ${(m.replies || []).map(x => `<p class="rep"><b>${esc(x.from_name || 'team')}:</b> ${esc(x.text || '')}</p>`).join('')}</div>`).join('')
      || '<p class="note">No messages yet.</p>';
  }

  async function send() {
    const text = el('relay-text').value.trim(), err = el('relay-err');
    err.textContent = '';
    if (!text) { err.textContent = 'Write a message first.'; el('relay-text').focus(); return; }
    if (!token) { err.textContent = 'The cstack server is not reachable.'; return; }
    sending = true; renderRelay();
    try {
      const res = await fetch(new URL('api/relay', base), {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Relay-Token': token},
        body: JSON.stringify({to: el('relay-to').value, text, about, client_id: crypto.randomUUID()})});
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
      el('relay-text').value = ''; about = null;
    } catch (e) { err.textContent = 'Not sent: ' + e.message; }
    sending = false; renderRelay();
  }

  el('relay-send').addEventListener('click', send);
  el('relay-text').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } });
  el('relay-text').addEventListener('input', () => { el('relay-err').textContent = ''; });
  el('relay-about').addEventListener('click', e => { if (e.target.closest('button')) { about = null; renderRelay(); } });
  // a section card can start a message about that part of the plant
  window.relayAbout = name => { about = name; renderRelay(); el('relay-text').focus(); el('relay').scrollIntoView({block: 'nearest'}); };
  window.renderRelay = renderRelay;
  renderRelay();
})();
