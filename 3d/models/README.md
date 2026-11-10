# Real models for the 3D battle

Put `.glb` files here and list them in `manifest.json`. A model replaces the placeholder shapes for that character.

```json
{
  "ondine": "ondine.glb",
  "caliste": { "file": "caliste.glb", "height": 2.4, "yaw": 0 },
  "hound": "hound.glb"
}
```

Names you can use: `ondine`, `caliste`, `maren`, `usher`, `hound`, `voice`, `reaver`.

Quick test without editing anything: drag a `.glb` onto the battle page and type the name.

## What the game does with your model
- Scales it to a fixed height (`height` in the manifest overrides it) and stands it on the floor.
- Expects it to face the +Z direction (the glTF default). If it faces the wrong way, set `"yaw"` in radians, for example `3.14159`.
- Swaps its materials for cel-shaded ones, keeping your textures, and can add a black outline on static meshes if you set `"outline": true` (it is off by default, because outlines show black patches on thin parts such as hair).
- Plays an animation named like `idle` in a loop (if there is one) and an animation named like `attack`, `strike`, `kick` or `punch` during attacks. If the file has just one animation that isn't an idle, it is used as the attack.
- Rigged (skinned) models get the toon look but no outline yet.
