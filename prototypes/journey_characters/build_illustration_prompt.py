#!/usr/bin/env python3
"""Build an English illustration prompt from a C-world recipe; no external calls."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys


def text_field(source, key, label):
    value = source[key]
    if (not isinstance(value, str) or not value.strip() or len(value) > 1200
            or any(ord(character) < 32 for character in value)):
        raise ValueError(label + " must be a nonempty, single-line string")
    return value.strip()


def select_recipe(document, index):
    if not isinstance(document, dict):
        raise ValueError("input must be a recipe object or a sample-output object")
    if "recipes" in document:
        recipes = document["recipes"]
        if not isinstance(recipes, list) or not 0 <= index < len(recipes):
            raise ValueError("recipe-index is outside the sample recipes")
        recipe = recipes[index]
    else:
        if index != 0:
            raise ValueError("a single recipe only supports recipe-index 0")
        recipe = document
    if not isinstance(recipe, dict):
        raise ValueError("selected recipe must be an object")
    return recipe


def build_prompt(recipe):
    """Project visual fields explicitly; never include raw location or road facts."""
    world = recipe["world"]
    if world["id"] != "translucent_keepsake_25d":
        raise ValueError("only the selected translucent_keepsake_25d C world is supported")
    character_id = recipe["characterId"]
    if not isinstance(character_id, str) or not re.fullmatch(r"nunti-[0-9a-f]{24}", character_id):
        raise ValueError("characterId must be a prototype-generated opaque nunti ID")
    recipe_hash = hashlib.sha256(json.dumps(recipe, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    design = recipe["design"]
    proportions = design["routeProportions"]
    width, height = proportions["widthMultiplier"], proportions["heightMultiplier"]
    for value in (width, height):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("body width and height multipliers must be positive finite numbers")
    palette = design["palette"]
    if (not isinstance(palette, list) or not palette
            or any(not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color) for color in palette)):
        raise ValueError("palette must contain hexadecimal RGB colors")
    interior = design["interiorIntent"]
    light = interior["light"]
    # The complete recipe is used only for the digest. Fields outside this visual
    # projection, including personality, voice, seed and driving facts, are not copied.
    return "\n".join([
        "INPUT METADATA, FOR TRACEABILITY ONLY; DO NOT DRAW OR LETTER THESE IDENTIFIERS",
        "character_id: " + character_id,
        "recipe_sha256: " + recipe_hash,
        "",
        "ILLUSTRATION PROMPT",
        "Create one original, very cute living travel companion in C art direction: a translucent commemorative keepsake in 2.5D.",
        "Use reference C only for its visual world and material language. Build this character's own silhouette from the recipe below.",
        "",
        "VISUAL WORLD",
        text_field(world, "renderIntent", "world.renderIntent") + ".",
        text_field(world, "interiorGrammar", "world.interiorGrammar") + ".",
        "",
        "BODY GEOMETRY, KEEP THE RECIPE SILHOUETTE DISTINCT",
        "Body family: " + text_field(design, "bodyFamily", "design.bodyFamily") + ".",
        "Shape recipe: " + text_field(design, "shapeId", "design.shapeId") + ".",
        "Dominant silhouette: " + text_field(design, "silhouette", "design.silhouette") + ".",
        "Relative body width multiplier: {:.3g}; relative body height multiplier: {:.3g}.".format(width, height),
        "The body shape itself carries the identity. Do not replace the shape difference with clothing or accessories.",
        "",
        "MATERIAL AND COLOR",
        "Shell material: " + text_field(design, "materialIntent", "design.materialIntent") + ".",
        "Use softly frosted translucent resin with rounded edges, gentle refraction and shallow visible depth.",
        "Palette, use as hues and never draw the color codes: " + ", ".join(palette) + ".",
        "",
        "LIVING FACE",
        "An opaque warm cream facial patch, two small widely spaced bead eyes, a tiny expressive mouth and restrained soft blush.",
        "Keep the face readable against the translucent body and give the companion a gentle, approachable expression.",
        "Face grammar from the recipe: " + text_field(world, "faceGrammar", "world.faceGrammar") + ".",
        "",
        "INNER KEEPSAKE DETAILS",
        "Suspended destination-inspired motif: " + text_field(interior, "destinationMotif", "interior.destinationMotif") + ".",
        "Internal pattern layout: " + text_field(interior, "routePattern", "interior.routePattern") + ".",
        "Inner light color: " + text_field(light, "color", "interior.light.color") + ".",
        "Inner light placement: " + text_field(light, "placement", "interior.light.placement") + ".",
        "Inner light diffusion: " + text_field(light, "diffusion", "interior.light.diffusion") + ".",
        "Use a few clear internal details. Preserve the face, soft body outline and small-size readability.",
        "",
        "CAMERA AND COMPOSITION",
        "Fixed front three-quarter orthographic view, full body visible, one companion centered with generous clear margins.",
        "Camera grammar from the recipe: " + text_field(world, "cameraIntent", "world.cameraIntent") + ".",
        "Render only this single living companion. No scene, display stand, packaging, comparison panels, UI, labels, logos, letters or other text.",
        "",
        "ACTUAL TRANSPARENT BACKGROUND",
        "Deliver a PNG with a real transparent alpha background outside the character and its minimal soft contact shadow.",
        "No opaque background, floor plane, environmental backdrop or painted checkerboard transparency pattern.",
        "",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--recipe-index", type=int, default=0)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.suffix.lower() != ".txt":
            raise ValueError("output must use a .txt suffix")
        document = json.loads(args.input.read_text(encoding="utf-8"))
        prompt = build_prompt(select_recipe(document, args.recipe_index))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prompt, encoding="utf-8")
        print("saved " + str(args.output))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("illustration prompt error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
