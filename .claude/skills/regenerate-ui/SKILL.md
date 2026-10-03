# Regenerate UI

Regenerate the Designer output after editing the `.ui` XML. `wflash/gui/main_window.ui` is the source of truth; `ui_main_window.py` is generated (CLAUDE.md, "GUI: Designer-first").

## Steps

1. Run pyside6-uic:
   ```bash
   ~/.venvs/wflash/bin/pyside6-uic wflash/gui/main_window.ui -o wflash/gui/ui_main_window.py
   ```

2. Verify the generated file imports cleanly:
   ```bash
   QT_QPA_PLATFORM=offscreen ~/.venvs/wflash/bin/python -c "import wflash.gui.ui_main_window"
   ```

3. Check that every `self.ui.<name>` referenced in the mixins still exists in the `.ui`:
   ```bash
   grep -ho 'self\.ui\.[A-Za-z_][A-Za-z0-9_]*' wflash/gui/*.py | sort -u | sed 's/self\.ui\.//' \
     | while read -r n; do grep -q "\"$n\"" wflash/gui/main_window.ui || echo "MISSING: $n"; done
   ```

4. Repeat 1-3 for any dialog `.ui` that changed (e.g. `settings_dialog.ui`).

5. Report success, or the errors found.

## Never

- Hand-edit `wflash/gui/ui_main_window.py` — it is generated and will be overwritten.
- Add a widget in Python that Designer could express. Dynamic content (mapping rows, log lines) is the only exception.
- Leave a Designer default name (`verticalLayout_2`, `label_5`) on a new widget.
