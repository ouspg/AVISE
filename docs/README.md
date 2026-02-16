# Documentation README

## Building the Documentation

1. Install dependencies:

   ```console
   python -m pip install -r requirements.txt
   python -m pip install -r docs/requirements-docs.txt
   ```

2. Build the documentation:

   ```console
   make -C docs/source html
   ```

   The HTML is created in the `docs/source/_build/html` directory.