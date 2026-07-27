# Jakub Preis website

This repository contains the static files for `www.jakubpreis.com`. It does
not require a build step.

## Preview locally

From the repository root, run:

```powershell
python -m http.server 8000
```

Then open <http://localhost:8000/>.

## Validate the site

Run the dependency-free link and HTML structure checks before publishing:

```powershell
python scripts/validate_site.py
```

The validator checks required page metadata, duplicate IDs, invalid block
elements inside paragraphs on hand-authored pages, active-link accessibility,
responsive image metadata, and all local `href`, `src`, `srcset`, and fragment
targets. HTML comments are excluded from link validation.
