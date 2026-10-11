<p align="center">
  <img src="docs/logo.png" width="96" alt="Recipes logo">
</p>

<h1 align="center">Recipes for Home Assistant</h1>

<p align="center">
  Keep your recipes in Home Assistant and put the ingredients on your shopping list with one tap.<br>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <img src="https://img.shields.io/github/v/release/martijnvanonz/ha-recipes" alt="Release">
  <img src="https://img.shields.io/github/actions/workflow/status/martijnvanonz/ha-recipes/tests.yml?label=tests" alt="Tests">
</p>

![Recipes overview](docs/screenshots/overview.jpg)

## Features

- **A Recipes tab in the sidebar** with a photo card for every recipe and a search box.
- **Add and edit recipes in the app**: photo (upload or take one with your phone), title, number of people, ingredients (amount · unit · name) and steps.
- **Add to shopping list**: pick the number of people and all amounts scale with it (`½ tin` → `1 tin`), untick what you already have, and the rest goes to your to-do list. Items that are already on the list are skipped.
- **A shopping list per person**: every Home Assistant user can choose their own to-do list (⚙️ in the tab).
- **Services for automations and AI agents**: `recipes.save`, `recipes.delete`, `recipes.list` and `recipes.add_to_shopping_list`, also over the REST API.
- **English and Dutch**. The tab follows the language of each user.
- **Local and private**: recipes are stored in `.storage/recipes` and photos in `config/recipes_photos/`. Both are part of your Home Assistant backups.

| Recipe | What do you need? |
|---|---|
| ![Recipe](docs/screenshots/recipe.jpg) | ![Add to shopping list](docs/screenshots/shopping-dialog.jpg) |

| Editor | On your phone |
|---|---|
| ![Editor](docs/screenshots/editor.jpg) | ![Mobile](docs/screenshots/mobile.jpg) |

## Install

**With HACS (recommended)**

1. In Home Assistant open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/martijnvanonz/ha-recipes` with type **Integration**.
3. Search for **Recipes**, click **Download** and restart Home Assistant.

**Manually**: copy `custom_components/recipes` into the `custom_components` folder of your configuration and restart.

Then go to **Settings → Devices & services → Add integration → Recipes** and pick the default shopping list (any to-do list, for example the built-in *Shopping list*). The **Recipes** tab appears in the sidebar.

## Services

```yaml
# Create a recipe (no id) or update one (with id; only the fields you give change)
action: recipes.save
data:
  title: Beef tacos
  servings: 2
  ingredients: |
    300 g minced beef
    1 red onion
    ½ tin sweetcorn
    6 tortillas
  steps:
    - Brown the beef in a large pan.
    - Warm the tortillas and fill them.
  photo_url: https://example.com/tacos.jpg   # or photo_base64 (base64 text or data URL)
response_variable: result                    # result.recipe.id

# Put the ingredients on the shopping list
action: recipes.add_to_shopping_list
data:
  title: tacos              # or id; a unique part of the title is enough
  servings: 4               # optional: scale the amounts
  exclude: [garlic]         # optional; or only: [...]
  shopping_list: todo.groceries   # optional; default from the integration settings
response_variable: added    # {added: [...], skipped: [...], shopping_list: ...}

# Get all recipes
action: recipes.list
response_variable: recipes

# Delete a recipe and its photo
action: recipes.delete
data:
  id: 0123456789abcdef0123456789abcdef
```

Over the REST API add `?return_response`, for example:

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title": "tacos", "servings": 4}' \
  "http://homeassistant.local:8123/api/services/recipes/add_to_shopping_list?return_response"
```

### Amounts

The amount at the start of an ingredient line is scaled. These forms work: `250`, `0,5`, `0.5`, `½`, `1½`, `1/2`, `1 1/2` and ranges like `2-3`. Lines without an amount (for example "salt and pepper") stay the same.

## Development

```bash
python -m pytest                    # tests
cd dev && docker compose up -d       # local Home Assistant on http://localhost:8124 (dev/ is not in git)
python scripts/make_brand.py         # icon and logo
```

Releases are automatic: raise `version` in `custom_components/recipes/manifest.json` and push to `main`. The release workflow then creates the tag and the GitHub release, and HACS offers the update.

## Credits

Food photos in the screenshots are from [Unsplash](https://unsplash.com) (Unsplash License):
[tacos](https://unsplash.com/photos/z_PfaGzeN9E),
[curry](https://unsplash.com/photos/sqcH2q7lkvo),
[pancakes](https://unsplash.com/photos/MytHEJlzdcM),
[pasta](https://unsplash.com/photos/ddZYOtZUnBk),
[salad](https://unsplash.com/photos/IGfIGP5ONV0),
[shakshuka](https://unsplash.com/photos/KD93b4XevCQ).

## License

[MIT](LICENSE)
