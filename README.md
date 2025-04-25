# selfOperatingComputer01
Testing out playwright on local machine
# Playwright headless browser and Codespaces

pip install playwright
playwright install chromium --with-deps

npx playwright test --ui --ui-host=0.0.0.0

John_computer_use.py creates a trace of the actions in trace.zip
this is "played" in playwright using
Inspect inside Codespaces (port-forward)
Run the Trace Viewer as a web server:

comp_use_003.py latest with lots of output - running commentary

npx playwright show-trace trace.zip \
  --host=0.0.0.0 \
  --port=9333