# Jarvis 007 memory brain

The dashboard's brain is a local perspective Canvas renderer: a gold cortical wire structure, cerebellum, brainstem, blue glow and depth-scaled memory dots. The wire structure is decorative; dots correspond to actual notes returned by the existing authenticated graph endpoint. Dot positions are deterministic visual placement, not semantic embeddings or claims about human brain anatomy. Only supplied graph links connect memories.

Background scenery adds calibration rings, edge circuitry, a perspective floor and a layered hologram projector. Wide screens also show panels with real memory/link/category counts. The Scene button hides the scenery. Background drawing is cached and never intercepts memory clicks.

Controls:
- Slow spin is on initially, except when the device requests reduced motion. The toggle pauses/resumes it.
- Drag to rotate; Shift-drag to pan. Scroll, pinch with two fingers, or use the plus/minus buttons to zoom (0.45–5×). Reset restores the initial camera.
- Hover shows a note label. Select a dot to inspect its title/path, then Open memory uses the existing dashboard note opener. Rotation pauses during inspection.
- With the canvas focused: arrows rotate, plus/minus zoom, 0 resets, Space toggles spin, Page Up/Down select memories, Enter selects/opens, Escape dismisses selection.

The existing category spotlight, voice/thinking methods, realtime graph updates, note counts and timelapse interface remain available. The renderer uses no remote libraries, generated image assets, paid tools or external telemetry. It draws at up to 30 fps during rotation and stops animation while hidden or the graph is paused.

## Review preview

Serve the repository locally and open `docs/previews/brain-spatial.html`. This is explicitly labeled fictional sample data; no account or brain data is loaded. The preview's Open memory dialog stands in for the dashboard's actual note opener.

## Validation on 20 October 2026

- New deterministic geometry, depth, camera, stable placement and classic-script integration tests passed.
- Existing JavaScript suite: 234/235 passed. `test_editor_cmds.js` fails the same three shortcut-label checks on untouched main as on this branch.
- Desktop and 390 × 844 layout visually inspected. Keyboard selection, note-opening callback, zoom controls and reset exercised in Chrome. Phone layout was checked in a desktop viewport, not on a physical iPhone; pinch behavior still needs a real-device acceptance check.
- Full `python tests/run.py` invoked but stopped by automatic approval review when an existing test attempted an unapproved Antigravity HTTPS connection. Full Python suite completion is not claimed.
- No changes deployed to the user's running installation. Main remains for the owner to merge through a PR.
