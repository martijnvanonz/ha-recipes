"""Fill the local dev Home Assistant with demo recipes (photos from dev/photos).

    .venv/bin/python scripts/seed_demo.py

Uses dev/token and http://localhost:8124. Deletes all existing recipes first.
"""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://localhost:8124/api/services/recipes"
TOKEN = (ROOT / "dev" / "token").read_text().strip()


def i(amount: str, unit: str, name: str) -> dict[str, str]:
    return {"amount": amount, "unit": unit, "name": name}


RECIPES = [
    ("pasta", "One-pot spinach pasta", 2,
     [i("250", "g", "pasta"), i("1", "", "onion"), i("2", "cloves", "garlic"), i("400", "ml", "vegetable stock"),
      i("250", "g", "frozen spinach"), i("125", "ml", "cooking cream"), i("50", "g", "parmesan"),
      i("2", "tbsp", "pine nuts"), i("", "", "salt and pepper")],
     ["Toast the pine nuts in a dry pan and set them aside.",
      "Chop the onion and garlic and fry them in a little oil for 2 minutes.",
      "Add the pasta, spinach, cream and hot stock. Bring to the boil.",
      "Cover and simmer for 10–15 minutes until the pasta is cooked, stirring now and then.",
      "Stir in the parmesan, season with salt and pepper and top with the pine nuts."]),
    ("tacos", "Beef tacos", 2,
     [i("300", "g", "minced beef"), i("1", "", "red onion"), i("2", "cloves", "garlic"), i("1", "", "bell pepper"),
      i("1", "sachet", "taco seasoning"), i("1", "tin", "chopped tomatoes"), i("½", "tin", "sweetcorn"),
      i("6", "", "tortillas"), i("1", "bunch", "coriander"), i("1", "", "lime")],
     ["Chop the onion, garlic and pepper.", "Brown the beef in a large pan.",
      "Add the onion and pepper and fry for 5 minutes.",
      "Stir in the garlic, taco seasoning, tomatoes and sweetcorn. Simmer for 10 minutes.",
      "Warm the tortillas, fill them and top with coriander and a squeeze of lime."]),
    ("pancakes", "Fluffy pancakes", 4,
     [i("250", "g", "flour"), i("2", "tsp", "baking powder"), i("2", "", "eggs"), i("300", "ml", "milk"),
      i("2", "tbsp", "sugar"), i("1", "pinch", "salt"), i("25", "g", "butter"), i("150", "g", "berries"),
      i("", "", "maple syrup")],
     ["Mix the flour, baking powder, sugar and salt.",
      "Whisk in the eggs and milk until smooth. Let the batter rest for 10 minutes.",
      "Melt a little butter in a pan and bake small pancakes for 2 minutes per side.",
      "Stack them up and serve with berries and maple syrup."]),
    ("curry", "Butter chicken curry", 4,
     [i("600", "g", "chicken thighs"), i("1", "", "onion"), i("3", "cloves", "garlic"), i("1", "piece", "ginger"),
      i("2", "tbsp", "curry paste"), i("1", "tin", "chopped tomatoes"), i("200", "ml", "cream"),
      i("40", "g", "butter"), i("300", "g", "basmati rice"), i("", "", "coriander")],
     ["Cut the chicken into pieces and fry in half of the butter until golden.",
      "Add the onion, garlic and ginger and fry for 3 minutes.",
      "Stir in the curry paste, then the tomatoes. Simmer for 15 minutes.",
      "Add the cream and the rest of the butter and simmer for 5 more minutes.",
      "Serve with basmati rice and coriander."]),
    ("shakshuka", "Shakshuka", 2,
     [i("1", "", "onion"), i("1", "", "red bell pepper"), i("2", "cloves", "garlic"), i("1", "tsp", "cumin"),
      i("1", "tsp", "paprika"), i("1", "tin", "chopped tomatoes"), i("4", "", "eggs"), i("50", "g", "feta"),
      i("", "", "parsley"), i("", "", "bread")],
     ["Fry the onion and pepper in olive oil until soft.", "Add the garlic, cumin and paprika and fry for 1 minute.",
      "Add the tomatoes and simmer for 10 minutes until thick.",
      "Make four wells and crack an egg into each. Cover and cook for 6–8 minutes.",
      "Top with feta and parsley and serve with bread."]),
    ("salad", "Rainbow salad bowl", 2,
     [i("1", "", "sweet potato"), i("1", "tin", "chickpeas"), i("1", "", "avocado"), i("150", "g", "cherry tomatoes"),
      i("¼", "", "red cabbage"), i("1", "", "yellow bell pepper"), i("100", "g", "lettuce"),
      i("2", "tbsp", "tahini"), i("1", "", "lemon")],
     ["Cut the sweet potato into cubes and roast at 200 °C for 25 minutes.",
      "Rinse the chickpeas and roast them for the last 10 minutes.", "Slice the vegetables and avocado.",
      "Whisk the tahini with lemon juice and a little water.", "Fill the bowls and drizzle with the dressing."]),
]


def call(service: str, data: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}/{service}?return_response",
        data=json.dumps(data).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp).get("service_response") or {}


def main() -> None:
    for recipe in call("list", {})["recipes"]:
        req = urllib.request.Request(
            f"{BASE}/delete", data=json.dumps({"id": recipe["id"]}).encode(),
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req).close()
    for photo, title, servings, ingredients, steps in RECIPES:
        b64 = base64.b64encode((ROOT / "dev" / "photos" / f"{photo}.jpg").read_bytes()).decode()
        call("save", {"title": title, "servings": servings, "ingredients": ingredients, "steps": steps,
                      "photo_base64": f"data:image/jpeg;base64,{b64}"})
        print("saved", title)


if __name__ == "__main__":
    main()
