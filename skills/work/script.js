// Behaviour of the Work status page, written into the page inline by build_page.py.
//
// The page shows one project tab, one view (a feature, or the decisions not linked to a
// feature), one part of that view (steps or decisions) and one group of decisions at a time.
// The address (#<id>) says what is shown, so links and the browser's back button work, and the
// last tab and view are remembered in localStorage. Decisions not settled can be answered: the
// answer is copied as an "Update decisions log: …" line, to paste into a chat.
//
// Everything is inside one block, so that its names do not become globals of the page.
{
  const tabs = [...document.querySelectorAll('.tabbtn')];

  // Show the tab of one project, and remember it.
  function show(slug) {
    for (const t of document.querySelectorAll('.tab')) {
      t.hidden = t.dataset.slug !== slug;
    }
    for (const b of tabs) {
      b.setAttribute('aria-selected', String(b.dataset.slug === slug));
    }
    try {
      localStorage.setItem('work-tab', slug);
    } catch (e) {}
  }

  // Show one set of the feature map: active features, past features, or the unlinked decisions.
  function showSet(tab, set) {
    for (const s of tab.querySelectorAll('.fset')) {
      s.hidden = s.dataset.set !== set;
    }
    tab.querySelector('.maphead').hidden = set === 'unlinked';
    for (const b of tab.querySelectorAll('.fsw')) {
      b.setAttribute('aria-pressed', String(b.dataset.set === set));
    }
  }

  // Show one part of a feature view: its steps or its decisions.
  function showPart(card, part) {
    for (const p of card.querySelectorAll('.panel')) {
      p.hidden = p.dataset.part !== part;
    }
    for (const b of card.querySelectorAll('.psw')) {
      b.setAttribute('aria-pressed', String(b.dataset.part === part));
    }
  }

  // Show one group of a feature's decisions: to take, taken, applied or replaced.
  function showGroup(card, group) {
    for (const g of card.querySelectorAll('.dgroup')) {
      g.hidden = g.dataset.group !== group;
    }
    for (const b of card.querySelectorAll('.dsw')) {
      b.setAttribute('aria-pressed', String(b.dataset.group === group));
    }
  }

  // Show one view of a tab, mark its row in the map, and remember it.
  function select(tab, view) {
    for (const v of tab.querySelectorAll('.view')) {
      v.hidden = v !== view;
    }
    for (const a of tab.querySelectorAll('.pick')) {
      const on = a.getAttribute('href') === '#' + view.id;
      a.classList.toggle('sel', on);
      a.closest('.frow')?.classList.toggle('sel', on);
      if (on && a.closest('.fset')) {
        showSet(tab, a.closest('.fset').dataset.set);
      }
    }
    if (view.id === tab.id + '-unlinked') {
      showSet(tab, 'unlinked');  // its toggle button is the only way to it
    }
    try {
      localStorage.setItem('work-view-' + tab.id, view.id);
    } catch (e) {}
  }

  // Show what the address names (#<tab>, #<feature>, #<tab>-decision-<n>, #<tab>-step-<n>…):
  // its tab, its view, the part and group it is in, and scroll to it with a short highlight.
  // Without one, the last tab and view shown, or the first ones.
  function route() {
    const h = decodeURIComponent(location.hash.slice(1));
    // the tab whose slug starts the address; the longest one wins, as one slug can start another
    let slug = '';
    for (const b of tabs) {
      const s = b.dataset.slug;
      if ((h === s || h.startsWith(s + '-')) && s.length > slug.length) {
        slug = s;
      }
    }
    if (!slug) {
      try {
        slug = localStorage.getItem('work-tab') || '';
      } catch (e) {}
    }
    if (!tabs.some(b => b.dataset.slug === slug)) {
      slug = tabs[0].dataset.slug;
    }
    show(slug);

    const tab = document.getElementById(slug);
    const el = h && h !== slug ? document.getElementById(h) : null;
    let view = el ? el.closest('.view') : null;
    if (!view) {
      try {
        view = document.getElementById(localStorage.getItem('work-view-' + slug) || '');
      } catch (e) {}
    }
    if (!view || !tab.contains(view)) {
      view = tab.querySelector('.view');
    }
    if (!view) {
      return;
    }
    select(tab, view);
    if (!el || el === view) {
      return;
    }

    // a step or decision: open the part and group it is in, then scroll to it
    const panel = el.closest('.panel');
    if (panel) {
      showPart(view, panel.dataset.part);
    }
    const group = el.closest('.dgroup');
    if (group) {
      showGroup(view, group.dataset.group);
    }
    for (let p = el; p; p = p.parentElement) {
      if (p.tagName === 'DETAILS') {
        p.open = true;
      }
    }
    el.scrollIntoView({block: 'start'});
    el.classList.add('hit');
    setTimeout(() => el.classList.remove('hit'), 2500);
  }

  // The project tabs change the address, and route() shows the tab.
  for (const b of tabs) {
    b.addEventListener('click', () => {
      location.hash = b.dataset.slug;
    });
  }

  // The switches of the feature map: active, past, unlinked.
  for (const b of document.querySelectorAll('.fsw')) {
    b.addEventListener('click', () => {
      const tab = b.closest('.tab');
      // the view below follows: the first feature of the list, or the unlinked decisions
      const first = tab.querySelector('.fset[data-set="' + b.dataset.set + '"] .pick');
      let target = '';
      if (b.dataset.set === 'unlinked') {
        target = '#' + tab.id + '-unlinked';
      } else if (first) {
        target = first.getAttribute('href');
      }
      if (!target) {
        showSet(tab, b.dataset.set);
      } else if (location.hash === target) {
        route();  // the same hash fires no hashchange
      } else {
        location.hash = target;
      }
    });
  }

  // The switches of a feature view (steps, decisions) and of its decision groups.
  for (const b of document.querySelectorAll('.psw')) {
    b.addEventListener('click', () => showPart(b.closest('.feature'), b.dataset.part));
  }
  for (const b of document.querySelectorAll('.dsw')) {
    b.addEventListener('click', () => showGroup(b.closest('.feature'), b.dataset.group));
  }

  // On narrow screens a table row is shown as a list: each cell gets its column's name, which
  // the CSS shows before it (data-l). Cells spanning several columns are counted as such.
  for (const c of document.querySelectorAll('.stack td:not([data-l])')) {
    let i = 0;
    let p = c;
    while ((p = p.previousElementSibling)) {
      i += p.colSpan;
    }
    c.dataset.l = c.closest('table').rows[0].cells[i]?.textContent || '';
  }

  addEventListener('hashchange', route);
  route();

  // Answers: pick an option or write your own, then copy it, to paste into the chat.

  // The "Update decisions log: …" line for a decision's answer panel, or '' with no answer yet.
  function answerText(dec) {
    const own = dec.querySelector('.other').value.trim();
    const picked = dec.querySelector('.pickopt[aria-checked=true]');
    let choice = '';
    if (own) {
      choice = 'Other: ' + own;
    } else if (picked) {
      choice = picked.dataset.answer;
    }
    if (!choice) {
      return '';
    }
    const change = dec.dataset.kind === 'Open' ? '' : ' (changes a ' + dec.dataset.kind + ' decision)';
    return 'Update decisions log: ' + dec.dataset.project + ' D' + dec.dataset.n
      + ' "' + dec.dataset.question + '": ' + choice + change;
  }

  // Pick one option: it replaces any other option picked and any words in the Other box.
  function pick(li) {
    const dec = li.closest('.dec');
    for (const o of dec.querySelectorAll('.pickopt')) {
      o.setAttribute('aria-checked', String(o === li));
    }
    dec.querySelector('.other').value = '';
    dec.querySelector('.send').disabled = false;
  }

  // Copy the answer line; where the browser refuses the clipboard, show it in a box to copy by hand.
  function copyAnswer(dec) {
    const text = answerText(dec);
    const msg = dec.querySelector('.sendmsg');
    const box = dec.querySelector('.copybox');
    if (!text) {
      return;
    }
    box.hidden = true;
    navigator.clipboard.writeText(text)
      .then(() => {
        msg.textContent = 'Copied: paste it into the chat.';
        dec.classList.add('sent');
      })
      .catch(() => {
        msg.textContent = 'The browser did not allow copying. Copy this and paste it into the chat:';
        box.value = text;
        box.hidden = false;
        box.select();
      });
  }

  // Clicks anywhere: an option (not a link inside it), Copy answer, or Answer/Change, which opens
  // or closes the answer panel in the row under the decision.
  document.addEventListener('click', e => {
    const li = e.target.closest('.pickopt');
    if (li && !e.target.closest('a')) {
      pick(li);
    }
    const b = e.target.closest('.send');
    if (b) {
      copyAnswer(b.closest('.dec'));
    }
    const o = e.target.closest('.opener');
    if (o) {
      const row = o.closest('tr').nextElementSibling;
      const open = row.hidden;
      row.hidden = !open;
      o.setAttribute('aria-expanded', String(open));
    }
  });

  // Enter or Space picks the option that has the keyboard focus.
  document.addEventListener('keydown', e => {
    const li = e.target.closest && e.target.closest('.pickopt');
    if (li && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      pick(li);
    }
  });

  // Words in the Other box unpick the options, and Copy answer is enabled while there is an answer.
  document.addEventListener('input', e => {
    if (!e.target.classList.contains('other')) {
      return;
    }
    const dec = e.target.closest('.dec');
    if (e.target.value.trim()) {
      for (const o of dec.querySelectorAll('.pickopt')) {
        o.setAttribute('aria-checked', 'false');
      }
    }
    dec.querySelector('.send').disabled = !answerText(dec);
  });
}
