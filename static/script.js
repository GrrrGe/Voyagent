'use strict';
const $ = (id) => document.getElementById(id);
const examples = {
  Tokyo: 'Plan 7 days in Tokyo from San Francisco under $2500 for 1 traveler, with food and walking.',
  Lisbon: 'Plan 5 days in Lisbon from New York under $1800 for 1 traveler, with history and walking.',
  Paris: 'Plan 4 days in Paris from Toronto under $1600 for 1 traveler, with art and history.'
};
const key = 'voyagent.thread_id';
let threadId = null;
let plan = null;
let busy = false;
let toastTimer;
try { threadId = localStorage.getItem(key); } catch { /* Storage can be disabled. */ }
const E = (tag, className = '', text = '') => {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== '') element.textContent = text;
  return element;
};
const append = (parent, ...children) => { parent.append(...children); return parent; };
const amount = (cents) => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(cents / 100);
const cost = (cents, source = 'MOCK') => `${amount(cents)} USD · ${source}`;
const time = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
const dateLabel = (value) => new Intl.DateTimeFormat('en-US', {month: 'short', day: 'numeric', year: 'numeric'}).format(new Date(`${value}T12:00:00`));
function toast(message) {
  $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4000);
}
function route(planner, replace = false) {
  $('landing').hidden = planner; $('planner').hidden = !planner;
  document.title = planner ? 'Your trip. Voyagent.' : 'Voyagent. A plan for the places ahead.';
  const path = planner ? '/planner' : '/';
  if (location.pathname !== path) history[replace ? 'replaceState' : 'pushState']({}, '', path);
}
function setBusy(value, message = 'Six agents are working through your trip. This may take a moment.') {
  busy = value;
  document.querySelectorAll('button[type="submit"], [data-example], [data-replan], #new-trip, #copy-plan, #pdf-plan').forEach(button => { button.disabled = value; });
  $('status').hidden = !value; $('status').textContent = message;
  document.querySelector('.results').setAttribute('aria-busy', String(value));
}
function showError(message) {
  $('error').textContent = message; $('error').hidden = false;
  $('error').scrollIntoView({block: 'center', behavior: 'smooth'});
}
async function request(url, options = {}) {
  const response = await fetch(url, {credentials: 'same-origin', ...options});
  if (!response.ok) {
    let message = `Request failed (${response.status}). Try again.`;
    try { const payload = await response.json(); if (typeof payload.detail === 'string') message = payload.detail; else if (Array.isArray(payload.detail)) message = 'Check the trip details and try again.'; } catch { /* Keep the status message. */ }
    const error = new Error(message); error.status = response.status; throw error;
  }
  return response;
}
function saveThread(value) {
  threadId = value;
  try { value ? localStorage.setItem(key, value) : localStorage.removeItem(key); } catch { toast('Browser storage is unavailable. Keep this page open to continue your trip.'); }
}
async function submitTrip(message, fresh = false) {
  if (busy) return;
  route(true); window.scrollTo({top: 0, behavior: 'smooth'});
  $('error').hidden = true; setBusy(true);
  try {
    const response = await request('/api/travel', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message, thread_id: fresh ? null : threadId})});
    plan = await response.json(); saveThread(plan.thread_id); renderPlan();
    $('replan-message').value = '';
  } catch (error) { showError(error.message || 'Could not reach the planner. Try again.'); }
  finally { setBusy(false); }
}
function tab(name, focus = false) {
  document.querySelectorAll('[data-tab]').forEach(button => {
    const active = button.dataset.tab === name;
    button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1;
    $(`panel-${button.dataset.tab}`).hidden = !active;
    if (active && focus) button.focus();
  });
}
function stat(label, value, detail) {
  return append(E('div', 'stat'), E('span', 'label', label), E('strong', '', value), E('small', '', detail));
}
function renderOverview() {
  const target = $('panel-overview'); target.replaceChildren();
  const photo = E('div', 'overview-photo'); const img = E('img');
  img.src = `/static/images/${plan.trip.destination.toLowerCase()}.jpg`; img.alt = `${plan.trip.destination} city view`;
  append(photo, img, E('span', 'image-tag', `${plan.trip.destination.toUpperCase()} / YOUR TRIP`));
  append(target, photo, E('p', 'overview-summary', plan.summary));
  const remaining = plan.budget.remaining_cents;
  append(target, append(E('div', 'stats-grid'),
    stat('ESTIMATED TOTAL', amount(plan.budget.total_cents), 'USD · MOCK'),
    stat('NIGHTS AWAY', String(plan.trip.days - 1), `${plan.selected_hotel.rooms} room(s)`),
    stat(remaining >= 0 ? 'BELOW YOUR BUDGET' : 'OVER YOUR BUDGET', amount(Math.abs(remaining)), 'USD · MOCK estimate')));
  const note = E('div', 'card result-card');
  append(note, E('h4', '', 'The assumptions.'), E('p', '', 'All costs are MOCK estimates in USD. Flights are round trip. Rooms hold two guests. Food, local transport, activities, and a 10% reserve are included. Dates are days at the destination. International travel may require extra days.'), E('p', 'day-note', 'Opening hours, exact transfer times, and availability need confirmation. This is a planning draft, not a booking.'));
  target.append(note);
  if (plan.changes.length) target.append(append(E('div', 'card result-card'), E('h4', '', 'What changed.'), ...plan.changes.map(change => E('p', 'change-note', change))));
}
function renderFlights() {
  const target = $('panel-flights'); target.replaceChildren();
  target.append(E('p', 'caption', 'Displayed fares are MOCK allowances. LIVE schedules, when enabled, are route research and may not match your dates.'));
  plan.flight_results.forEach(flight => {
    const card = E('article', 'card result-card');
    append(card, E('div', 'selected-label', `${flight.id === plan.selected_flight.id ? 'IN YOUR PLAN · ' : ''}${flight.data_source} RESEARCH`), E('h4', '', `${flight.airline}.`), E('p', '', `${flight.number} · ${flight.stops === 0 ? 'Nonstop demo allowance' : 'One-stop demo allowance'}`));
    const routeLine = E('div', 'route-line');
    append(routeLine, append(E('div'), E('strong', '', flight.origin), E('p', '', plan.trip.origin)), E('span', '', '↗'), append(E('div'), E('strong', '', flight.destination), E('p', '', plan.trip.destination)));
    append(card, routeLine, E('strong', 'price', amount(flight.price_cents)), E('span', 'price-label', `USD · ${flight.price_source} · ${flight.price_basis}`), E('p', 'day-note', `Outbound departure: ${flight.departure}. Arrival: ${flight.arrival}.`), E('p', 'day-note', flight.note));
    target.append(card);
  });
}
function renderHotels() {
  const target = $('panel-hotels'); target.replaceChildren();
  plan.hotel_results.forEach(hotel => {
    const card = E('article', 'card result-card');
    append(card, E('div', 'selected-label', `${hotel.id === plan.selected_hotel.id ? 'IN YOUR PLAN · ' : ''}${hotel.data_source} RESEARCH`), E('h4', '', `${hotel.name.replace(/\.$/, '')}.`), E('p', '', `${hotel.area} · ${hotel.rooms} room(s) · ${plan.trip.days - 1} nights`), E('strong', 'price', amount(hotel.nightly_cents)), E('span', 'price-label', `USD · ${hotel.price_source} · per room per night`), E('p', 'day-note', hotel.note));
    if (hotel.url) {
      try {
        const url = new URL(hotel.url);
        if (url.protocol === 'https:') { const link = E('a', 'button soft', 'View source ↗'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link); }
      } catch { /* Omit invalid source links. */ }
    }
    target.append(card);
  });
}
function renderItinerary() {
  const target = $('panel-itinerary'); target.replaceChildren();
  plan.itinerary.forEach(day => {
    const card = E('article', 'card result-card');
    append(card, append(E('div', 'day-heading'), E('span', 'day-number', String(day.day).padStart(2, '0')), append(E('div'), E('h4', '', `${day.area}.`), E('p', 'caption', dateLabel(day.date)))));
    day.events.forEach(event => {
      append(card, append(E('div', 'event'), E('time', '', `${time(event.start)} to ${time(event.end)}`), append(E('div'), E('strong', '', event.title), E('small', '', `${cost(event.cost_cents, event.price_source)} per person · ${event.indoor ? 'Indoors' : 'Outdoors'}`))));
    });
    if (!day.events.length) card.append(E('p', '', 'No scheduled visits. This day is reserved for the changed travel window.'));
    card.append(E('p', 'day-note', day.note)); target.append(card);
  });
}
function renderBudget() {
  const target = $('panel-budget'); target.replaceChildren();
  const budget = plan.budget; const card = E('article', 'card result-card');
  append(card, E('p', 'eyebrow', 'ALL TRAVELERS. ALL TRIP DAYS.'), E('h3', '', 'The numbers.'), E('div', 'budget-total', amount(budget.total_cents)), E('span', 'price-label', 'USD · MOCK ESTIMATE'));
  const meter = E('meter', 'budget-meter'); meter.min = 0; meter.max = Math.max(budget.limit_cents, budget.total_cents); meter.value = budget.total_cents; meter.setAttribute('aria-label', `Estimated spend ${amount(budget.total_cents)}. Budget ${amount(budget.limit_cents)}.`); card.append(meter);
  card.append(E('p', budget.within_budget ? 'budget-status saving' : 'budget-status', `${amount(Math.abs(budget.remaining_cents))} USD ${budget.within_budget ? 'below' : 'over'} your budget. MOCK estimate.`));
  budget.items.forEach(item => card.append(append(E('div', 'budget-row'), E('span', '', item.category), append(E('span'), E('strong', '', amount(item.amount_cents)), E('small', '', item.price_source)))));
  if (budget.savings_cents) card.append(E('p', 'saving', `${cost(budget.savings_cents)} saved by replacing paid visits.`));
  append(card, E('p', 'day-note', 'Hotel estimate includes taxes. Food is $35.00 USD MOCK per person per day. Local transport is $12.00 USD MOCK per person per day. The reserve is 10% of all other costs, rounded up to a cent.'), E('p', 'day-note', 'Visa fees, insurance, shopping, and transport to your departure airport are excluded.'));
  target.append(card);
}
function renderPlan() {
  $('empty-state').hidden = true; $('plan-content').hidden = false;
  $('trip-kicker').textContent = `${plan.trip.days} DAYS / ${plan.trip.travelers} TRAVELER${plan.trip.travelers === 1 ? '' : 'S'}`;
  $('trip-title').textContent = `${plan.trip.destination}. On the calendar.`;
  $('trip-meta').textContent = `${plan.trip.origin} → ${plan.trip.destination} · ${dateLabel(plan.trip.start_date)} to ${dateLabel(plan.trip.end_date)}`;
  $('agent-trace').replaceChildren(...plan.trace.map(name => E('span', '', `✓ ${name}`)));
  renderOverview(); renderFlights(); renderHotels(); renderItinerary(); renderBudget();
  $('changes').replaceChildren(...plan.changes.map(change => E('p', 'change-note', change)));
  $('destination').value = plan.trip.destination; $('origin').value = plan.trip.origin; $('days').value = plan.trip.days;
  $('travelers').value = plan.trip.travelers; $('budget').value = plan.trip.budget_cents / 100; $('start-date').value = plan.trip.start_date;
  tab('overview');
}
$('hero-form').addEventListener('submit', event => { event.preventDefault(); submitTrip($('trip-message').value, true); });
$('planner-form').addEventListener('submit', event => {
  event.preventDefault();
  submitTrip(`Plan ${$('days').value} days in ${$('destination').value} from ${$('origin').value} on ${$('start-date').value} for ${$('travelers').value} travelers under $${$('budget').value}, with ${$('interests').value}.`);
});
$('replan-form').addEventListener('submit', event => { event.preventDefault(); submitTrip($('replan-message').value); });
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => submitTrip(examples[button.dataset.example], true)));
document.querySelectorAll('[data-replan]').forEach(button => button.addEventListener('click', () => submitTrip(button.dataset.replan)));
document.querySelectorAll('[data-tab]').forEach(button => {
  button.addEventListener('click', () => tab(button.dataset.tab));
  button.addEventListener('keydown', event => {
    const tabs = [...document.querySelectorAll('[data-tab]')]; let index = tabs.indexOf(button);
    if (event.key === 'ArrowRight') index = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') index = (index + tabs.length - 1) % tabs.length;
    else if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = tabs.length - 1;
    else return;
    event.preventDefault(); tab(tabs[index].dataset.tab, true);
  });
});
$('new-trip').addEventListener('click', () => {
  saveThread(null); plan = null; $('plan-content').hidden = true; $('empty-state').hidden = false; $('error').hidden = true;
  $('planner-form').reset(); setDefaultDate(); $('destination').focus(); toast('A new trip is ready to plan.');
});
$('copy-plan').addEventListener('click', async () => {
  if (!plan) return;
  try { await navigator.clipboard.writeText(plan.answer); toast('Trip plan copied.'); }
  catch { showError('Clipboard access is unavailable. Export a PDF to save your plan.'); }
});
$('pdf-plan').addEventListener('click', async () => {
  if (!plan || busy) return;
  const button = $('pdf-plan'); button.disabled = true; button.textContent = 'Preparing PDF';
  try {
    const response = await request(`/api/travel/${threadId}/pdf`); const blob = await response.blob();
    const url = URL.createObjectURL(blob); const link = E('a'); link.href = url; link.download = `Voyagent-${plan.trip.destination}.pdf`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000); toast('Your PDF is ready.');
  } catch (error) { showError(error.message); }
  finally { button.disabled = false; button.textContent = 'Export PDF ↗'; }
});
function setDefaultDate() {
  const localISO = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const today = new Date(); $('start-date').min = localISO(today); today.setDate(today.getDate() + 30); $('start-date').value = localISO(today);
}
window.addEventListener('popstate', () => route(location.pathname === '/planner', true));
async function init() {
  setDefaultDate(); route(location.pathname === '/planner', true);
  request('/health').then(response => response.json()).then(health => {
    const live = Object.entries(health.providers).filter(([, mode]) => mode === 'LIVE').map(([name]) => name);
    if (live.length) $('provider-note').textContent = `LIVE research: ${live.join(', ')}. Unverified price allowances stay MOCK.`;
  }).catch(() => { $('provider-note').textContent = 'Planner connection unavailable. Try again shortly.'; });
  if (threadId && location.pathname === '/planner') {
    setBusy(true, 'Opening your saved trip.');
    try { plan = await (await request(`/api/travel/${threadId}`)).json(); renderPlan(); }
    catch (error) { if (error.status === 404 || error.status === 422) saveThread(null); showError(error.message); }
    finally { setBusy(false); }
  }
}
init();
