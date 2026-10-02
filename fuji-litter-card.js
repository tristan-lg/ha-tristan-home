/**
 * Fuji Litter Card
 * ----------------
 * A hand-drawn style Lovelace card for a litter box monitored by the
 * "Fuji" custom integration (presence sensor + last visit sensor + history
 * sensor). Inspired by the layout/spirit of sionetta/wm_animated_ha_card:
 * an animated illustration on top, a status badge below it, and a short
 * "last cycles" summary at the bottom.
 *
 * No build step, no dependencies: a single vanilla custom element using
 * Shadow DOM, relying on <ha-card> for native Home Assistant theming
 * (light/dark follows the active HA theme automatically).
 */

const DEFAULT_COOLDOWN_MINUTES = 15;

const STATE_LABELS = {
  absence: 'Absence',
  presence: 'Présence',
  pipi: 'Pipi',
  caca: 'Caca',
};

const STATE_EMOJI = {
  absence: '🚫',
  presence: '🐈',
  pipi: '💧',
  caca: '💩',
};

const VISIT_EMOJI = {
  Pipi: '💧',
  Caca: '💩',
};

function clampToArray(value) {
  return Array.isArray(value) ? value : [];
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.round(Number(totalSeconds) || 0));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatElapsedShort(ms) {
  const minutes = Math.round(ms / 60000);
  if (minutes <= 0) return "à l'instant";
  if (minutes === 1) return 'il y a 1 min';
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  if (hours < 24) {
    return rem > 0 ? `il y a ${hours} h ${rem} min` : `il y a ${hours} h`;
  }
  const days = Math.floor(hours / 24);
  return `il y a ${days} j`;
}

function formatVisitTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return '';

  const now = new Date();
  const sameDay = (a, b) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  const time = date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });

  if (sameDay(date, now)) return `Aujourd'hui ${time}`;
  if (sameDay(date, yesterday)) return `Hier ${time}`;
  return `${date.toLocaleDateString(undefined, {
    day: '2-digit',
    month: '2-digit',
  })} ${time}`;
}

class FujiLitterCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: 'custom:fuji-litter-card',
      name: 'Litière Fuji',
      presence_entity: 'binary_sensor.fuji_presence',
      last_visit_entity: 'sensor.fuji_last_visit',
      history_entity: 'sensor.fuji_history',
    };
  }

  static getConfigElement() {
    return document.createElement('fuji-litter-card-editor');
  }

  setConfig(config) {
    if (!config || !config.presence_entity) {
      throw new Error('fuji-litter-card: "presence_entity" est requis.');
    }
    if (!config.last_visit_entity) {
      throw new Error('fuji-litter-card: "last_visit_entity" est requis.');
    }

    this._config = {
      name: 'Litière',
      cooldown_minutes: DEFAULT_COOLDOWN_MINUTES,
      history_entity: this._guessHistoryEntity(config.last_visit_entity),
      current_duration_entity: null,
      history_count: 3,
      ...config,
    };

    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
      this._buildStaticDom();
    }
    this._lastRenderKey = null;
    this._render();
  }

  _guessHistoryEntity(lastVisitEntity) {
    if (typeof lastVisitEntity !== 'string') return undefined;
    if (lastVisitEntity.endsWith('_last_visit')) {
      return lastVisitEntity.replace(/_last_visit$/, '_history');
    }
    return undefined;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  connectedCallback() {
    this._tickTimer = window.setInterval(() => this._render(), 1000 * 15);
  }

  disconnectedCallback() {
    if (this._tickTimer) {
      window.clearInterval(this._tickTimer);
      this._tickTimer = null;
    }
  }

  _buildStaticDom() {
    const style = document.createElement('style');
    style.textContent = CARD_CSS;

    const card = document.createElement('ha-card');
    card.innerHTML = `
      <div class="fuji-card">
        <div class="illustration" part="illustration"></div>
        <div class="status-row">
          <div class="status-emoji"></div>
          <div class="status-text">
            <div class="status-main"></div>
            <div class="status-sub"></div>
          </div>
        </div>
        <div class="history"></div>
      </div>
    `;

    this.shadowRoot.append(style, card);
    this._els = {
      card,
      illustration: card.querySelector('.illustration'),
      statusEmoji: card.querySelector('.status-emoji'),
      statusMain: card.querySelector('.status-main'),
      statusSub: card.querySelector('.status-sub'),
      history: card.querySelector('.history'),
    };
  }

  _computeState() {
    const hass = this._hass;
    const config = this._config;
    if (!hass || !config) return null;

    const presenceState = hass.states[config.presence_entity];
    const lastVisitState = hass.states[config.last_visit_entity];

    const isPresent = !!presenceState && presenceState.state === 'on';
    const lastVisitType = lastVisitState ? lastVisitState.state : 'Aucun';
    const attrs = (lastVisitState && lastVisitState.attributes) || {};

    const cooldownMinutes = Number(config.cooldown_minutes);
    const now = Date.now();
    let isFresh = false;
    if ((lastVisitType === 'Pipi' || lastVisitType === 'Caca') && attrs.ended_at) {
      const endedAt = new Date(attrs.ended_at).getTime();
      if (!Number.isNaN(endedAt)) {
        isFresh =
          cooldownMinutes <= 0 || now - endedAt <= cooldownMinutes * 60000;
      }
    }

    let key = 'absence';
    if (isPresent) {
      key = 'presence';
    } else if (isFresh) {
      key = lastVisitType === 'Caca' ? 'caca' : 'pipi';
    }

    // Live duration of the current visit, prefer a dedicated sensor if given.
    let currentDurationSeconds = null;
    if (isPresent) {
      if (config.current_duration_entity && hass.states[config.current_duration_entity]) {
        currentDurationSeconds = Number(
          hass.states[config.current_duration_entity].state
        );
      } else if (presenceState.last_changed) {
        currentDurationSeconds =
          (now - new Date(presenceState.last_changed).getTime()) / 1000;
      }
    }

    const historyEntityId = config.history_entity;
    const historyState = historyEntityId ? hass.states[historyEntityId] : null;
    const visits = clampToArray(
      historyState && historyState.attributes && historyState.attributes.visits
    ).slice(0, Math.max(0, Number(config.history_count) || 3));

    return {
      key,
      isPresent,
      lastVisitType,
      lastVisitAttrs: attrs,
      currentDurationSeconds,
      visits,
    };
  }

  _render() {
    if (!this.shadowRoot || !this._els || !this._hass || !this._config) return;

    const state = this._computeState();
    if (!state) return;

    this._els.card.header = this._config.name;

    this._els.illustration.innerHTML = ILLUSTRATIONS[state.key] || ILLUSTRATIONS.absence;
    this._els.illustration.className = `illustration state-${state.key}`;

    this._els.statusEmoji.textContent = STATE_EMOJI[state.key];
    this._els.statusMain.textContent = STATE_LABELS[state.key];

    this._els.statusSub.textContent = this._computeSubText(state);

    this._renderHistory(state.visits);
  }

  _computeSubText(state) {
    if (state.key === 'presence') {
      if (state.currentDurationSeconds != null && !Number.isNaN(state.currentDurationSeconds)) {
        return `Depuis ${formatDuration(state.currentDurationSeconds)}`;
      }
      return 'En cours...';
    }

    if (state.key === 'pipi' || state.key === 'caca') {
      const { duration_seconds: duration, ended_at: endedAt } = state.lastVisitAttrs;
      const parts = [];
      if (duration != null) parts.push(`durée ${formatDuration(duration)}`);
      if (endedAt) {
        const elapsedMs = Date.now() - new Date(endedAt).getTime();
        if (!Number.isNaN(elapsedMs)) parts.push(formatElapsedShort(elapsedMs));
      }
      return parts.join(' · ');
    }

    // Absence: show a hint about the last concluant visit, if any.
    const { duration_seconds: duration, ended_at: endedAt } = state.lastVisitAttrs;
    if (state.lastVisitType === 'Pipi' || state.lastVisitType === 'Caca') {
      const elapsedMs = endedAt ? Date.now() - new Date(endedAt).getTime() : null;
      const elapsed = elapsedMs != null && !Number.isNaN(elapsedMs)
        ? formatElapsedShort(elapsedMs)
        : '';
      return [`Dernier passage : ${state.lastVisitType}`, elapsed]
        .filter(Boolean)
        .join(' ');
    }
    return 'Aucun passage enregistré';
  }

  _renderHistory(visits) {
    if (!visits.length) {
      this._els.history.innerHTML = '<div class="history-empty">Pas encore de passage enregistré.</div>';
      return;
    }

    const rows = visits
      .map((visit) => {
        const emoji = VISIT_EMOJI[visit.type] || '🐾';
        const duration = formatDuration(visit.duration_seconds);
        const time = formatVisitTime(visit.ended_at);
        return `
          <div class="history-row">
            <span class="history-emoji">${emoji}</span>
            <span class="history-type">${visit.type}</span>
            <span class="history-duration">${duration}</span>
            <span class="history-time">${time}</span>
          </div>
        `;
      })
      .join('');

    this._els.history.innerHTML = `<div class="history-title">Derniers passages</div>${rows}`;
  }
}

// ---------------------------------------------------------------------------
// Illustrations (inline SVG, one per state key)
// ---------------------------------------------------------------------------

const BOX_SHAPE = `
  <path class="box-shadow" d="M20 108c0 6 36 11 80 11s80-5 80-11-36-11-80-11-80 5-80 11z"/>
  <path class="box-back" d="M38 46 h124 v18 c0 4 -4 8 -10 8 h-104 c-6 0 -10 -4 -10 -8 z"/>
  <path class="box-body" d="M30 64 h140 l-10 44 c-1 5 -5 8 -10 8 h-100 c-5 0 -9 -3 -10 -8 z"/>
  <path class="box-rim" d="M28 58 c0 -5 5 -9 12 -9 h120 c7 0 12 4 12 9 s-5 9 -12 9 h-120 c-7 0 -12 -4 -12 -9 z"/>
  <path class="box-sand" d="M44 66 h112 l-6 30 h-100 z"/>
`;

const ILLUSTRATIONS = {
  absence: `
    <svg viewBox="0 0 200 130" preserveAspectRatio="xMidYMid meet">
      ${BOX_SHAPE}
      <g class="sand-grains">
        <circle cx="70" cy="80" r="1.6"/>
        <circle cx="90" cy="86" r="1.6"/>
        <circle cx="112" cy="79" r="1.6"/>
        <circle cx="130" cy="88" r="1.6"/>
        <circle cx="100" cy="92" r="1.6"/>
      </g>
    </svg>
  `,
  presence: `
    <svg viewBox="0 0 200 130" preserveAspectRatio="xMidYMid meet">
      ${BOX_SHAPE}
      <g class="cat">
        <ellipse class="cat-body" cx="100" cy="70" rx="34" ry="20"/>
        <circle class="cat-head" cx="100" cy="46" r="18"/>
        <path class="cat-ear" d="M86 34 l-6 -14 l14 8 z"/>
        <path class="cat-ear" d="M114 34 l6 -14 l-14 8 z"/>
        <path class="cat-face" d="M92 46 q8 6 16 0" />
        <circle class="cat-eye" cx="93" cy="44" r="1.8"/>
        <circle class="cat-eye" cx="107" cy="44" r="1.8"/>
        <path class="cat-tail" d="M130 72 q22 -4 18 -22"/>
      </g>
    </svg>
  `,
  pipi: `
    <svg viewBox="0 0 200 130" preserveAspectRatio="xMidYMid meet">
      ${BOX_SHAPE}
      <g class="poof">
        <circle cx="100" cy="30" r="14"/>
        <circle cx="82" cy="36" r="9"/>
        <circle cx="120" cy="36" r="9"/>
      </g>
      <text x="100" y="37" class="emoji-mark" text-anchor="middle">💧</text>
    </svg>
  `,
  caca: `
    <svg viewBox="0 0 200 130" preserveAspectRatio="xMidYMid meet">
      ${BOX_SHAPE}
      <g class="poof">
        <circle cx="100" cy="30" r="14"/>
        <circle cx="82" cy="36" r="9"/>
        <circle cx="120" cy="36" r="9"/>
      </g>
      <text x="100" y="37" class="emoji-mark" text-anchor="middle">💩</text>
    </svg>
  `,
};

const CARD_CSS = `
  :host {
    display: block;
  }
  .fuji-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 8px 16px 16px;
  }
  .illustration {
    display: flex;
    justify-content: center;
    align-items: flex-end;
    height: 150px;
  }
  .illustration svg {
    width: 220px;
    max-width: 100%;
    height: auto;
    overflow: visible;
  }

  .box-shadow { fill: var(--divider-color, #0000001a); opacity: 0.35; }
  .box-back { fill: var(--fuji-box-back, #c9c0b3); }
  .box-body { fill: var(--fuji-box-body, #ded5c6); }
  .box-rim { fill: var(--fuji-box-rim, #b8ac99); }
  .box-sand { fill: var(--fuji-sand, #efe6d3); }
  .sand-grains circle { fill: var(--fuji-box-rim, #b8ac99); opacity: 0.6; }

  .state-presence .box-sand { fill: var(--fuji-sand, #efe6d3); }
  .cat-body, .cat-head { fill: var(--fuji-cat, #6b5b4a); }
  .cat-ear { fill: var(--fuji-cat, #6b5b4a); }
  .cat-tail { fill: none; stroke: var(--fuji-cat, #6b5b4a); stroke-width: 6; stroke-linecap: round; }
  .cat-face { fill: none; stroke: var(--fuji-cat-face, #2b2420); stroke-width: 1.4; stroke-linecap: round; }
  .cat-eye { fill: var(--fuji-cat-face, #2b2420); }

  .poof circle { fill: var(--fuji-poof, #ffffff); opacity: 0.9; filter: drop-shadow(0 1px 1px rgba(0,0,0,0.08)); }
  .emoji-mark { font-size: 20px; dominant-baseline: middle; }

  .status-row {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--secondary-background-color, #0000000d);
    border-radius: 14px;
    padding: 10px 14px;
  }
  .status-emoji { font-size: 28px; line-height: 1; }
  .status-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .status-main {
    font-size: 15px;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .status-sub {
    font-size: 12.5px;
    color: var(--secondary-text-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .history { display: flex; flex-direction: column; gap: 4px; }
  .history-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--secondary-text-color);
    margin-bottom: 2px;
  }
  .history-empty { font-size: 13px; color: var(--secondary-text-color); }
  .history-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 2px;
    border-top: 1px solid var(--divider-color, #0000001a);
    font-size: 13px;
    color: var(--primary-text-color);
  }
  .history-row:first-of-type { border-top: none; }
  .history-emoji { font-size: 16px; }
  .history-type { flex: 0 0 auto; width: 44px; color: var(--secondary-text-color); }
  .history-duration { flex: 0 0 auto; font-variant-numeric: tabular-nums; }
  .history-time { margin-left: auto; color: var(--secondary-text-color); }
`;

if (!customElements.get('fuji-litter-card')) {
  customElements.define('fuji-litter-card', FujiLitterCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'fuji-litter-card',
  name: 'Fuji Litter Card',
  description:
    "Carte illustrée pour la litière Fuji : présence, dernier passage (pipi/caca) et historique.",
});
