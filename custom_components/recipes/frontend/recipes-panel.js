// Recipes panel for Home Assistant. Plain web component, no build step.
// Views: list -> detail -> (edit | add-to-shopping-list dialog).

const STRINGS = {
  en: {
    title: "Recipes",
    new: "New recipe",
    search: "Search recipes",
    empty: "No recipes yet. Tap 'New recipe' to add one.",
    noMatch: "No recipe matches your search.",
    people: (n) => (n === 1 ? "1 person" : `${n} people`),
    ingredientsCount: (n) => (n === 1 ? "1 ingredient" : `${n} ingredients`),
    ingredients: "Ingredients",
    steps: "Steps",
    addToList: "Add to shopping list",
    edit: "Edit",
    delete: "Delete",
    confirmDelete: "Tap again to delete",
    back: "Back",
    whatToAdd: "What do you need?",
    forPeople: "For",
    all: "All",
    none: "None",
    addN: (n) => (n === 1 ? "Add 1 item" : `Add ${n} items`),
    cancel: "Cancel",
    added: (a, s) => `Added ${a}` + (s ? ` · ${s} already on the list` : ""),
    nothingAdded: (s) => (s ? `Everything is already on the list (${s})` : "Nothing added"),
    editTitle: "Edit recipe",
    newTitle: "New recipe",
    photo: "Photo",
    choosePhoto: "Choose photo",
    changePhoto: "Change photo",
    removePhoto: "Remove photo",
    uploading: "Uploading…",
    name: "Title",
    servings: "Number of people",
    ingredientsHelp: "One per line, amount first (e.g. 250 g pasta)",
    stepsHelp: "One step per line",
    save: "Save",
    saved: "Recipe saved",
    deleted: "Recipe deleted",
    needTitle: "Please enter a title",
    noIngredients: "This recipe has no ingredients yet.",
  },
  nl: {
    title: "Recepten",
    new: "Nieuw recept",
    search: "Zoek recepten",
    empty: "Nog geen recepten. Tik op 'Nieuw recept' om er een toe te voegen.",
    noMatch: "Geen recept gevonden.",
    people: (n) => (n === 1 ? "1 persoon" : `${n} personen`),
    ingredientsCount: (n) => (n === 1 ? "1 ingrediënt" : `${n} ingrediënten`),
    ingredients: "Ingrediënten",
    steps: "Bereiding",
    addToList: "Op boodschappenlijst",
    edit: "Bewerken",
    delete: "Verwijderen",
    confirmDelete: "Tik nog eens om te verwijderen",
    back: "Terug",
    whatToAdd: "Wat heb je nodig?",
    forPeople: "Voor",
    all: "Alles",
    none: "Niets",
    addN: (n) => (n === 1 ? "Voeg 1 toe" : `Voeg ${n} toe`),
    cancel: "Annuleren",
    added: (a, s) => `${a} toegevoegd` + (s ? ` · ${s} stond er al op` : ""),
    nothingAdded: (s) => (s ? `Alles stond er al op (${s})` : "Niets toegevoegd"),
    editTitle: "Recept bewerken",
    newTitle: "Nieuw recept",
    photo: "Foto",
    choosePhoto: "Kies foto",
    changePhoto: "Andere foto",
    removePhoto: "Foto weg",
    uploading: "Uploaden…",
    name: "Titel",
    servings: "Aantal personen",
    ingredientsHelp: "Eén per regel, hoeveelheid vooraan (bijv. 250 g pasta)",
    stepsHelp: "Eén stap per regel",
    save: "Opslaan",
    saved: "Recept opgeslagen",
    deleted: "Recept verwijderd",
    needTitle: "Vul een titel in",
    noIngredients: "Dit recept heeft nog geen ingrediënten.",
  },
};

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class RecipesPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._recipes = [];
    this._view = "list";
    this._current = null;
    this._search = "";
    this._loaded = false;
    this._draft = null;
    this._dialog = null;
    this._confirmDelete = false;
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
    this.shadowRoot.addEventListener("input", (e) => this._onInput(e));
    this.shadowRoot.addEventListener("change", (e) => this._onChange(e));
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._render();
      this._load();
    }
  }

  set narrow(value) {
    if (this._narrow === value) return;
    this._narrow = value;
    if (this._hass) this._render();
  }

  get _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
    return STRINGS[lang] || STRINGS.en;
  }

  async _load() {
    try {
      const res = await this._hass.callWS({ type: "recipes/list" });
      this._recipes = res.recipes;
      if (this._current) this._current = this._recipes.find((r) => r.id === this._current.id) || null;
      if (!this._current && this._view === "detail") this._view = "list";
    } catch (err) {
      this._toast(err.message || String(err));
    }
    this._loaded = true;
    this._render();
  }

  // ---------- events ----------

  _onClick(e) {
    const el = e.target.closest("[data-action]");
    if (!el) return;
    const action = el.dataset.action;
    const t = this._t;
    switch (action) {
      case "menu":
        this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "open":
        this._current = this._recipes.find((r) => r.id === el.dataset.id);
        this._view = "detail";
        this._confirmDelete = false;
        this._render();
        this.shadowRoot.querySelector(".content")?.scrollTo(0, 0);
        break;
      case "back":
        this._view = this._view === "edit" && this._current ? "detail" : "list";
        this._draft = null;
        this._render();
        break;
      case "new":
        this._draft = { title: "", servings: 2, ingredients: "", steps: "", photo: null, photo_url: null };
        this._current = null;
        this._view = "edit";
        this._render();
        break;
      case "edit": {
        const r = this._current;
        this._draft = {
          id: r.id,
          title: r.title,
          servings: r.servings,
          ingredients: r.ingredients.join("\n"),
          steps: r.steps.join("\n"),
          photo: r.photo,
          photo_url: r.photo_url,
        };
        this._view = "edit";
        this._render();
        break;
      }
      case "delete":
        if (!this._confirmDelete) {
          this._confirmDelete = true;
          this._render();
          return;
        }
        this._delete();
        break;
      case "pick-photo":
        this.shadowRoot.querySelector("#photo-input").click();
        break;
      case "remove-photo":
        this._draft.photo = null;
        this._draft.photo_url = null;
        this._render();
        break;
      case "save":
        this._save();
        break;
      case "open-add":
        this._openAdd();
        break;
      case "close-dialog":
        this._dialog = null;
        this._render();
        break;
      case "servings-down":
      case "servings-up":
        this._setDialogServings(this._dialog.servings + (action === "servings-up" ? 1 : -1));
        break;
      case "select-all":
      case "select-none":
        this._dialog.selected = this._dialog.items.map(() => action === "select-all");
        this._render();
        break;
      case "confirm-add":
        this._confirmAdd();
        break;
      case "backdrop":
        if (e.target === el) {
          this._dialog = null;
          this._render();
        }
        break;
    }
  }

  _onInput(e) {
    const field = e.target.dataset.field;
    if (field === "search") {
      this._search = e.target.value;
      this._renderList();
      return;
    }
    if (this._draft && field) this._draft[field] = e.target.value;
  }

  _onChange(e) {
    if (e.target.id === "photo-input" && e.target.files?.length) this._upload(e.target.files[0]);
    const idx = e.target.dataset.item;
    if (idx !== undefined) {
      this._dialog.selected[Number(idx)] = e.target.checked;
      this._renderDialogButton();
    }
  }

  // ---------- actions ----------

  async _upload(file) {
    this._draft.uploading = true;
    this._render();
    try {
      const body = new FormData();
      body.append("file", file);
      const resp = await this._hass.fetchWithAuth("/api/recipes/photo", { method: "POST", body });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.message || resp.statusText);
      this._draft.photo = data.photo;
      this._draft.photo_url = `/api/recipes/photos/${data.photo}`;
    } catch (err) {
      this._toast(err.message || String(err));
    }
    this._draft.uploading = false;
    this._render();
  }

  async _save() {
    const d = this._draft;
    const t = this._t;
    if (!d.title.trim()) {
      this._toast(t.needTitle);
      return;
    }
    const lines = (s) => s.split("\n").map((l) => l.trim()).filter(Boolean);
    const msg = {
      type: "recipes/save",
      title: d.title.trim(),
      servings: Math.max(1, Math.min(50, parseInt(d.servings, 10) || 1)),
      ingredients: lines(d.ingredients),
      steps: lines(d.steps),
      photo: d.photo || null,
    };
    if (d.id) msg.recipe_id = d.id;
    try {
      const res = await this._hass.callWS(msg);
      this._current = res.recipe;
      this._draft = null;
      this._view = "detail";
      this._toast(t.saved);
      await this._load();
    } catch (err) {
      this._toast(err.message || String(err));
    }
  }

  async _delete() {
    try {
      await this._hass.callWS({ type: "recipes/delete", recipe_id: this._current.id });
      this._current = null;
      this._view = "list";
      this._toast(this._t.deleted);
      await this._load();
    } catch (err) {
      this._toast(err.message || String(err));
    }
  }

  async _openAdd() {
    const r = this._current;
    this._dialog = { servings: r.servings, items: [...r.ingredients], selected: r.ingredients.map(() => true) };
    this._render();
  }

  async _setDialogServings(n) {
    n = Math.max(1, Math.min(50, n));
    const dlg = this._dialog;
    dlg.servings = n;
    try {
      const res = await this._hass.callWS({ type: "recipes/scale", recipe_id: this._current.id, servings: n });
      dlg.items = res.ingredients;
    } catch (err) {
      this._toast(err.message || String(err));
    }
    this._render();
  }

  async _confirmAdd() {
    const dlg = this._dialog;
    const items = dlg.items.filter((_, i) => dlg.selected[i]);
    if (!items.length) return;
    try {
      const res = await this._hass.callWS({ type: "recipes/add_to_shopping_list", items });
      const t = this._t;
      this._toast(res.added.length ? t.added(res.added.length, res.skipped.length) : t.nothingAdded(res.skipped.length));
      this._dialog = null;
      this._render();
    } catch (err) {
      this._toast(err.message || String(err));
    }
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
  }

  // ---------- rendering ----------

  _render() {
    if (!this._hass) return;
    const t = this._t;
    let body = "";
    let title = t.title;
    let left = this._narrow
      ? `<button class="icon" data-action="menu" aria-label="menu"><ha-icon icon="mdi:menu"></ha-icon></button>`
      : "";
    let right = "";
    if (this._view === "list") {
      right = `<button class="primary small" data-action="new"><ha-icon icon="mdi:plus"></ha-icon><span>${t.new}</span></button>`;
      body = this._listHtml();
    } else if (this._view === "detail" && this._current) {
      left = `<button class="icon" data-action="back" aria-label="${t.back}"><ha-icon icon="mdi:arrow-left"></ha-icon></button>`;
      title = esc(this._current.title);
      right = `<button class="icon" data-action="edit" aria-label="${t.edit}"><ha-icon icon="mdi:pencil"></ha-icon></button>`;
      body = this._detailHtml();
    } else if (this._view === "edit") {
      left = `<button class="icon" data-action="back" aria-label="${t.back}"><ha-icon icon="mdi:close"></ha-icon></button>`;
      title = this._draft?.id ? t.editTitle : t.newTitle;
      right = `<button class="primary small" data-action="save"><span>${t.save}</span></button>`;
      body = this._editHtml();
    }
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">${left}<div class="title">${title}</div>${right}</div>
      <div class="content">${body}</div>
      ${this._dialog ? this._dialogHtml() : ""}`;
    if (this._view === "list") {
      const input = this.shadowRoot.querySelector("#search");
      if (input && this._searchFocus) {
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      }
    }
  }

  _filtered() {
    const q = this._search.trim().toLowerCase();
    if (!q) return this._recipes;
    return this._recipes.filter(
      (r) => r.title.toLowerCase().includes(q) || r.ingredients.some((i) => i.toLowerCase().includes(q))
    );
  }

  _cardsHtml() {
    const t = this._t;
    const list = this._filtered();
    if (!this._loaded) return "";
    if (!this._recipes.length) return `<p class="empty">${t.empty}</p>`;
    if (!list.length) return `<p class="empty">${t.noMatch}</p>`;
    return list
      .map(
        (r) => `
        <button class="card" data-action="open" data-id="${esc(r.id)}">
          ${r.photo_url ? `<img src="${esc(r.photo_url)}" alt="" loading="lazy">` : `<div class="placeholder"><ha-icon icon="mdi:silverware-fork-knife"></ha-icon></div>`}
          <div class="card-text">
            <div class="card-title">${esc(r.title)}</div>
            <div class="meta">${t.people(r.servings)} · ${t.ingredientsCount(r.ingredients.length)}</div>
          </div>
        </button>`
      )
      .join("");
  }

  _listHtml() {
    const t = this._t;
    const search = this._recipes.length > 4
      ? `<div class="search"><ha-icon icon="mdi:magnify"></ha-icon><input id="search" data-field="search" placeholder="${t.search}" value="${esc(this._search)}"></div>`
      : "";
    return `${search}<div class="grid" id="grid">${this._cardsHtml()}</div>`;
  }

  _renderList() {
    const grid = this.shadowRoot.querySelector("#grid");
    if (grid) grid.innerHTML = this._cardsHtml();
  }

  _detailHtml() {
    const t = this._t;
    const r = this._current;
    const ingredients = r.ingredients.length
      ? `<ul class="ingredients">${r.ingredients.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>`
      : `<p class="muted">${t.noIngredients}</p>`;
    const steps = r.steps.length
      ? `<h2>${t.steps}</h2><ol class="steps">${r.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>`
      : "";
    return `
      <div class="detail">
        ${r.photo_url ? `<img class="hero" src="${esc(r.photo_url)}" alt="">` : ""}
        <h1>${esc(r.title)}</h1>
        <div class="meta big"><ha-icon icon="mdi:account-group"></ha-icon> ${t.people(r.servings)}</div>
        <button class="primary wide" data-action="open-add" ${r.ingredients.length ? "" : "disabled"}>
          <ha-icon icon="mdi:cart-plus"></ha-icon><span>${t.addToList}</span>
        </button>
        <div class="columns">
          <section><h2>${t.ingredients}</h2>${ingredients}</section>
          <section>${steps}</section>
        </div>
        <div class="danger-zone">
          <button class="text danger" data-action="delete">
            <ha-icon icon="mdi:delete"></ha-icon><span>${this._confirmDelete ? t.confirmDelete : t.delete}</span>
          </button>
        </div>
      </div>`;
  }

  _editHtml() {
    const t = this._t;
    const d = this._draft;
    const photo = d.uploading
      ? `<div class="photo-box"><span class="muted">${t.uploading}</span></div>`
      : d.photo_url
        ? `<div class="photo-box"><img src="${esc(d.photo_url)}" alt=""></div>`
        : `<button class="photo-box" data-action="pick-photo"><ha-icon icon="mdi:camera-plus"></ha-icon><span>${t.choosePhoto}</span></button>`;
    return `
      <div class="form">
        <label>${t.photo}</label>
        ${photo}
        <div class="row">
          ${d.photo_url ? `<button class="text" data-action="pick-photo"><ha-icon icon="mdi:camera"></ha-icon><span>${t.changePhoto}</span></button>
          <button class="text danger" data-action="remove-photo"><ha-icon icon="mdi:close"></ha-icon><span>${t.removePhoto}</span></button>` : ""}
        </div>
        <input id="photo-input" type="file" accept="image/*" hidden>
        <label for="f-title">${t.name}</label>
        <input id="f-title" data-field="title" value="${esc(d.title)}" autocomplete="off">
        <label for="f-servings">${t.servings}</label>
        <input id="f-servings" data-field="servings" type="number" min="1" max="50" inputmode="numeric" value="${esc(d.servings)}">
        <label for="f-ingredients">${t.ingredients}</label>
        <div class="help">${t.ingredientsHelp}</div>
        <textarea id="f-ingredients" data-field="ingredients" rows="8" placeholder="250 g pasta&#10;1 ui">${esc(d.ingredients)}</textarea>
        <label for="f-steps">${t.steps}</label>
        <div class="help">${t.stepsHelp}</div>
        <textarea id="f-steps" data-field="steps" rows="8">${esc(d.steps)}</textarea>
        <button class="primary wide" data-action="save"><span>${t.save}</span></button>
      </div>`;
  }

  _dialogHtml() {
    const t = this._t;
    const dlg = this._dialog;
    const count = dlg.selected.filter(Boolean).length;
    return `
      <div class="backdrop" data-action="backdrop">
        <div class="dialog" role="dialog" aria-modal="true">
          <div class="dialog-head">
            <h2>${t.whatToAdd}</h2>
            <button class="icon" data-action="close-dialog" aria-label="${t.cancel}"><ha-icon icon="mdi:close"></ha-icon></button>
          </div>
          <div class="stepper">
            <span>${t.forPeople}</span>
            <button class="icon round" data-action="servings-down" ${dlg.servings <= 1 ? "disabled" : ""}><ha-icon icon="mdi:minus"></ha-icon></button>
            <strong>${t.people(dlg.servings)}</strong>
            <button class="icon round" data-action="servings-up"><ha-icon icon="mdi:plus"></ha-icon></button>
          </div>
          <div class="row select-row">
            <button class="text" data-action="select-all">${t.all}</button>
            <button class="text" data-action="select-none">${t.none}</button>
          </div>
          <div class="items">
            ${dlg.items
              .map(
                (item, i) => `
              <label class="item">
                <input type="checkbox" data-item="${i}" ${dlg.selected[i] ? "checked" : ""}>
                <span>${esc(item)}</span>
              </label>`
              )
              .join("")}
          </div>
          <button class="primary wide" id="add-button" data-action="confirm-add" ${count ? "" : "disabled"}>
            <ha-icon icon="mdi:cart-plus"></ha-icon><span>${t.addN(count)}</span>
          </button>
        </div>
      </div>`;
  }

  _renderDialogButton() {
    const btn = this.shadowRoot.querySelector("#add-button");
    if (!btn) return;
    const count = this._dialog.selected.filter(Boolean).length;
    btn.disabled = !count;
    btn.querySelector("span").textContent = this._t.addN(count);
  }
}

const STYLE = `
  :host { display: block; height: 100%; background: var(--primary-background-color); color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  * { box-sizing: border-box; }
  button { font: inherit; color: inherit; cursor: pointer; }
  button:disabled { opacity: .45; cursor: default; }
  .toolbar { display: flex; align-items: center; gap: 4px; height: var(--header-height, 56px); padding: 0 8px 0 12px;
             background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff);
             border-bottom: var(--app-header-border-bottom, none); position: sticky; top: 0; z-index: 2;
             padding-top: env(safe-area-inset-top); }
  .toolbar .title { flex: 1; font-size: 20px; font-weight: 400; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-left: 8px; }
  .toolbar .primary.small { background: rgba(255,255,255,.18); color: inherit; }
  .content { height: calc(100% - var(--header-height, 56px)); overflow-y: auto; padding: 16px; padding-bottom: calc(24px + env(safe-area-inset-bottom)); }
  .icon { background: none; border: none; width: 40px; height: 40px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }
  .icon:hover { background: rgba(127,127,127,.15); }
  .icon.round { border: 1px solid var(--divider-color); }
  .primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border: none; border-radius: 20px;
             padding: 0 18px; height: 40px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; font-weight: 500; }
  .primary.small { height: 36px; padding: 0 14px; }
  .primary.wide { width: 100%; height: 48px; border-radius: 24px; font-size: 16px; margin: 16px 0; }
  .text { background: none; border: none; color: var(--primary-color); padding: 8px; display: inline-flex; align-items: center; gap: 6px; font-weight: 500; }
  .danger { color: var(--error-color, #db4437); }
  .muted, .help { color: var(--secondary-text-color); }
  .help { font-size: 13px; margin: -2px 0 6px; }
  .empty { text-align: center; color: var(--secondary-text-color); margin-top: 48px; }
  .search { display: flex; align-items: center; gap: 8px; background: var(--card-background-color); border-radius: 24px;
            padding: 0 16px; height: 44px; margin: 0 auto 16px; max-width: 1200px; border: 1px solid var(--divider-color); }
  .search input { border: none; outline: none; background: none; color: inherit; font: inherit; flex: 1; height: 100%; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; max-width: 1200px; margin: 0 auto; }
  .card { background: var(--card-background-color); border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color));
          border-radius: var(--ha-card-border-radius, 12px); padding: 0; overflow: hidden; text-align: left; display: flex; flex-direction: column;
          box-shadow: var(--ha-card-box-shadow, none); }
  .card img, .placeholder { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; }
  .placeholder { display: flex; align-items: center; justify-content: center; background: rgba(127,127,127,.12); color: var(--secondary-text-color);
                 --mdc-icon-size: 40px; }
  .card-text { padding: 10px 12px 12px; }
  .card-title { font-weight: 500; line-height: 1.25; }
  .meta { color: var(--secondary-text-color); font-size: 13px; margin-top: 4px; }
  .meta.big { font-size: 15px; display: flex; align-items: center; gap: 6px; --mdc-icon-size: 20px; }
  .detail { max-width: 900px; margin: 0 auto; }
  .hero { width: 100%; max-height: 420px; object-fit: cover; border-radius: var(--ha-card-border-radius, 12px); display: block; }
  h1 { font-size: 26px; font-weight: 500; margin: 16px 0 4px; }
  h2 { font-size: 18px; font-weight: 500; margin: 8px 0; }
  .columns { display: grid; grid-template-columns: 1fr; gap: 8px 32px; }
  @media (min-width: 760px) { .columns { grid-template-columns: 2fr 3fr; } .detail .primary.wide { width: auto; padding: 0 28px; } }
  .ingredients { padding-left: 20px; margin: 0; line-height: 1.6; }
  .steps { padding-left: 22px; margin: 0; line-height: 1.55; }
  .steps li { margin-bottom: 10px; }
  .danger-zone { margin-top: 32px; border-top: 1px solid var(--divider-color); padding-top: 8px; }
  .form { max-width: 640px; margin: 0 auto; display: flex; flex-direction: column; }
  .form label { font-weight: 500; margin: 14px 0 6px; }
  .form input:not([type=file]), .form textarea { font: inherit; color: inherit; background: var(--card-background-color);
         border: 1px solid var(--divider-color); border-radius: 8px; padding: 10px 12px; width: 100%; }
  .form textarea { resize: vertical; line-height: 1.5; }
  .form input:focus, .form textarea:focus { outline: 2px solid var(--primary-color); outline-offset: -1px; }
  .photo-box { width: 100%; aspect-ratio: 16 / 9; border: 2px dashed var(--divider-color); border-radius: 12px; background: none;
               display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; overflow: hidden;
               color: var(--secondary-text-color); --mdc-icon-size: 36px; }
  .photo-box img { width: 100%; height: 100%; object-fit: cover; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; }
  .backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 10; display: flex; align-items: flex-end; justify-content: center; }
  @media (min-width: 600px) { .backdrop { align-items: center; } }
  .dialog { background: var(--card-background-color, var(--primary-background-color)); width: 100%; max-width: 480px; max-height: 90vh;
            border-radius: 20px 20px 0 0; padding: 16px 20px calc(8px + env(safe-area-inset-bottom)); display: flex; flex-direction: column; }
  @media (min-width: 600px) { .dialog { border-radius: 20px; } }
  .dialog-head { display: flex; align-items: center; justify-content: space-between; }
  .stepper { display: flex; align-items: center; gap: 12px; margin: 8px 0; }
  .stepper strong { min-width: 96px; text-align: center; }
  .select-row { margin: 4px -8px; }
  .items { overflow-y: auto; border-top: 1px solid var(--divider-color); border-bottom: 1px solid var(--divider-color); }
  .item { display: flex; align-items: center; gap: 12px; padding: 12px 4px; border-bottom: 1px solid var(--divider-color); cursor: pointer; }
  .item:last-child { border-bottom: none; }
  .item input { width: 20px; height: 20px; accent-color: var(--primary-color); flex: none; }
`;

customElements.define("recipes-panel", RecipesPanel);
