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

  // Search: a popup that finds a step or decision in any project, by number or words, and shows
  // its links: the steps a step waits on, blocks and is connected to, and what a decision is
  // linked to. Each link opens in the popup in turn, and Back goes to the one before. The data is
  // the JSON that build_page.py writes into the page (keys "<project slug>:S<n>" and ":D<n>").

  const index = JSON.parse(document.getElementById('work-index').textContent);
  const dialog = document.querySelector('dialog.search');
  const query = dialog.querySelector('.sq');
  const projectBox = dialog.querySelector('.spick');
  const results = dialog.querySelector('.sresults');
  const item = dialog.querySelector('.sitem');
  const names = Object.fromEntries(index.projects.map(p => [p.slug, p.name]));
  const order = index.projects.map(p => p.slug);
  const trail = [];  // the items opened before the one shown, for Back
  let current = '';

  // The step or decision of a key, or undefined when it is not on the page (dropped, or not in WIP.md).
  function entry(key) {
    return key.includes(':S') ? index.steps[key] : index.decisions[key];
  }

  // An element with a class and a text.
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    e.className = cls;
    e.textContent = text || '';
    return e;
  }

  // The keys of the steps and decisions that match the search, by project (in the tabs' order),
  // steps first, newest first: a number (S87, D314 or 87), or words that a step's text and
  // feature, or a decision's question, all have, in the project chosen in the dropdown (or all).
  // A project's name and a number ("project-2 S55") is that project's step or decision,
  // whatever the dropdown says; the longest name is tried first, as one name can end another.
  function find(q) {
    const named = index.projects.slice().sort((a, b) => b.name.length - a.name.length)
      .find(p => q.toLowerCase().startsWith(p.name.toLowerCase() + ' ') && /^[sd]\s*\d+$/i.test(q.slice(p.name.length).trim()));
    const only = named ? named.slug : projectBox.value;  // '' is every project
    const num = (named ? q.slice(named.name.length).trim() : q).match(/^([sd])?\s*(\d+)$/i);
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const found = [];
    for (const [kind, list] of [['S', index.steps], ['D', index.decisions]]) {
      for (const [key, e] of Object.entries(list)) {
        if (only && e.p !== only) {
          continue;
        }
        const text = (kind === 'S' ? e.text + ' ' + e.feature : e.question).toLowerCase();
        if (num ? (!num[1] || num[1].toUpperCase() === kind) && e.n === Number(num[2]) : words.every(w => text.includes(w))) {
          found.push(key);
        }
      }
    }
    const rank = key => [order.indexOf(entry(key).p), key.includes(':S') ? 0 : 1, -entry(key).n];
    return found.sort((a, b) => {
      const [x, y] = [rank(a), rank(b)];
      return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
    });
  }

  // The features of a step or decision as one text, each with how it got a decision.
  function featureText(e) {
    const list = e.features.map(f => f.name + (f.how ? ' (' + f.how + ')' : ''));
    return list.length ? 'Feature: ' + list.join('; ') : 'No feature';
  }

  // The features of an opened step or decision, under its title: each a link to it on the page.
  function featureLines(e) {
    if (!e.features.length) {
      return [el('p', 'smeta', 'No feature')];
    }
    return e.features.map(f => {
      const p = el('p', 'smeta', 'Feature: ');
      const a = el('a', 'sfeat', f.name);
      a.href = f.href;
      p.append(a, f.how ? ' (' + f.how + ')' : '');
      return p;
    });
  }

  // The project, number and status of a step or decision, as three small elements.
  function badges(key) {
    const at = key.lastIndexOf(':');
    // a decision "Replaced by D…" is tagged Replaced; a step keeps its whole status ("Not started")
    const status = key.includes(':S') ? entry(key).status : entry(key).status.split(' ')[0];
    const cls = key.includes(':S') ? (status === 'Done' ? 't-done' : 't-todo') : 't-' + status.toLowerCase();
    return [el('span', 'sproj', names[key.slice(0, at)] || key.slice(0, at)), el('span', 'num', key.slice(at + 1)), el('span', 'tag ' + cls, status)];
  }

  // One line for a step or decision: its project, number, status and text, as a button that
  // opens it in the popup, with a note after it; a plain line when it is not on the page.
  function line(key, note) {
    const li = document.createElement('li');
    const e = entry(key);
    const at = key.lastIndexOf(':');
    const project = names[key.slice(0, at)] || key.slice(0, at);
    if (!e) {
      li.append(el('span', 'gone', project + ' ' + key.slice(at + 1) + ' (not on the page)'));
      return li;
    }
    const b = el('button', 'sopen');
    b.type = 'button';
    b.dataset.key = key;
    b.append(...badges(key), el('span', 'stext', key.includes(':S') ? e.text : e.question), el('span', 'sfline', featureText(e)));
    li.append(b);
    if (note) {
      li.append(el('span', 'snote' + (note.includes('no longer') ? ' free' : ''), note));
    }
    return li;
  }

  // A titled list of links in the item view; "None" when it is empty. Each link is a key, or a
  // [key, note] pair.
  function group(title, links) {
    const ul = el('ul', 'slist');
    for (const l of links) {
      ul.append(Array.isArray(l) ? line(l[0], l[1]) : line(l));
    }
    if (!links.length) {
      ul.append(el('li', 'gone', 'None'));
    }
    return [el('h3', 'sgroup', title), ul];
  }

  // The note of a blocking link: where it was read from, and "no longer blocking" when the
  // step that blocks is done.
  function blockNote(source, blocker) {
    const from = source === 'marker' ? 'from its After marker' : 'guessed from the wording';
    return blocker && blocker.status.startsWith('Done') ? from + '; done, no longer blocking' : from;
  }

  // The list of results for what is typed in the box.
  function showResults() {
    const q = query.value.trim();
    const found = q ? find(q) : [];
    item.hidden = true;
    results.hidden = false;
    results.replaceChildren();
    if (!q) {
      return;
    }
    const ul = el('ul', 'slist');
    for (const key of found.slice(0, 100)) {
      ul.append(line(key));
    }
    const count = found.length > 100 ? found.length + ' found, the first 100 shown' : found.length + ' found';
    results.append(el('p', 'scount', count), ul);
  }

  // One step or decision and its links.
  function showItem(key) {
    const e = entry(key);
    const step = key.includes(':S');
    const bar = el('div', 'sacts');
    const back = el('button', 'sbtn sback', 'Back');  // to the item before, or to the results
    current = key;
    back.type = 'button';
    bar.append(back);
    if (e.href) {
      const a = el('a', 'sbtn', 'Show on page');
      a.href = e.href;
      bar.append(a);
    }
    // the whole text as the title, with its project, number, status (and date) and feature under it
    const id = el('p', 'sid');
    id.append(...badges(key), step ? '' : el('span', 'smeta', e.date));
    item.replaceChildren(bar, el('h2', 'stitle', step ? e.text : e.question), id, ...featureLines(e));
    if (step) {
      item.append(...group('Waits on', e.waits.map(([k, source]) => [k, blockNote(source, entry(k))])),
        ...group('Blocks', e.blocks.map(([k, source]) => [k, blockNote(source, e)])),
        ...group('Connected, without blocking', e.connected),
        ...group('Decisions it links to', e.decisions));
    } else {
      item.append(el('p', 'sfull', e.chosen ? 'Decision: ' + e.chosen : 'No option chosen yet.'),
        ...group('Steps that link to it', e.linked),
        ...group('Steps named in its row', e.named),
        ...group('Updates', e.updates),
        ...group('Updated by', e.updated_by));
    }
    results.hidden = true;
    item.hidden = false;
    item.scrollTop = 0;
    dialog.querySelector('.sback').focus();
  }

  document.querySelector('.searchbtn').addEventListener('click', () => {
    dialog.showModal();
    query.focus();
    query.select();
  });
  query.addEventListener('input', () => {
    trail.length = 0;
    showResults();
  });
  projectBox.addEventListener('change', () => {
    trail.length = 0;
    showResults();
  });

  // In the popup: a result or link opens that item, Back the one before (or the results), and a
  // link to the page closes the popup and shows it there. A click outside the popup closes it:
  // the dark area around it is part of the dialog element, as is its padding, so its box decides.
  dialog.addEventListener('click', e => {
    const box = dialog.getBoundingClientRect();
    if (e.target === dialog && (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom)) {
      dialog.close();
      return;
    }
    const open = e.target.closest('.sopen');
    const a = e.target.closest('a');
    if (open && open.dataset.key !== current) {
      if (!item.hidden) {
        trail.push(current);
      }
      showItem(open.dataset.key);
    } else if (e.target.closest('.sback')) {
      if (trail.length) {
        showItem(trail.pop());
      } else {
        current = '';
        showResults();
      }
    } else if (a) {
      dialog.close();
      if (a.getAttribute('href') === location.hash) {
        route();  // the same hash fires no hashchange
      }
    }
  });
}
