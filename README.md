# Recipes for Home Assistant

Keep your recipes in Home Assistant and put the ingredients on your shopping list.

- **Recipes tab** in the sidebar: browse recipes with photos, add and edit them (photo, title, number of people, ingredients, steps).
- **Add to shopping list**: choose the number of people (amounts are scaled), tick what you need, and the items go to a to-do list. Items that are already on the list are skipped.
- **Services** for automations and AI agents: `recipes.save`, `recipes.delete`, `recipes.list`, `recipes.add_to_shopping_list`.
- English and Dutch. Data lives in `.storage/recipes`, photos in `config/recipes_photos/` (both in your HA backups).

## Install

Copy `custom_components/recipes` to your HA config (or add this repo to HACS as a custom repository), restart, then add the **Recipes** integration and pick your shopping list.

## Services

```yaml
# Create (no id) or update (with id; only the given fields change)
action: recipes.save
data:
  title: Taco wraps
  servings: 2
  ingredients: |
    300 g minced beef
    1 red onion
    wraps
  steps:
    - Chop the onion.
    - Fry the beef.
  photo_url: https://example.com/taco.jpg   # or photo_base64
response_variable: result   # result.recipe.id

action: recipes.add_to_shopping_list
data:
  title: taco          # or id; a unique part of the title is enough
  servings: 4          # scale the amounts
  exclude: [garlic]    # or only: [...]
response_variable: added   # {added: [...], skipped: [...]}

action: recipes.list       # returns all recipes
response_variable: recipes
```

Over the REST API: `POST /api/services/recipes/list?return_response`.

Amounts at the start of a line are scaled: `250 g`, `½`, `1½`, `1/2`, `0,5`, `2-3`. Lines without an amount (for example "salt and pepper") stay the same.

## Development

```bash
python -m pytest
```
