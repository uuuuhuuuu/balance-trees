# Publish Rotation Lab with GitHub Pages

Target repository: [vaclavkouril/balance-trees](https://github.com/vaclavkouril/balance-trees).
After the first successful deployment, the public visualizer will be at:

**https://vaclavkouril.github.io/balance-trees/**

## One-time GitHub setup

1. Open [Settings → Pages](https://github.com/vaclavkouril/balance-trees/settings/pages).
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Open [Actions → Publish Rotation Lab](https://github.com/vaclavkouril/balance-trees/actions/workflows/pages.yml).
4. Select **Run workflow**, keep the default branch, and run it. This also retries
   the initial deployment if it started before Pages was enabled.
5. Wait for both jobs to pass. Open the deployment URL shown by the workflow.

No custom secrets, hosting account, npm installation, or Python server are needed
for the public website. The workflow uses GitHub's automatically provided token.
These are GitHub's [custom workflow publishing instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Future updates

Push source changes to the repository's default branch. The workflow tests the
Python implementations and browser models, prepares the public files, and
publishes them automatically. It discovers the default branch; it is not tied
to the name `main`. Pull requests and other branches are checked without
publishing to the live site. Documentation-only changes do not trigger deployment;
use **Run workflow** whenever you need a manual deployment.

The public site contains treaps, all ten BST strategies, sequence presets,
CSV input/import, playback, and trace import/export. Simulation runs in each
visitor's browser. To show an exact Python run, export a JSON trace locally and
import it into the website. See [the showcase guide](showcase.md).

## Preview the public build locally

From the repository root:

```sh
PYTHONPATH=src python -m balance_trees.showcase.build --output _site
python -m http.server --directory _site 8000
```

Open `http://127.0.0.1:8000`. Use a fresh output directory for each build, or remove
the previously generated `_site` directory before rebuilding. It is ignored by
Git; the workflow always builds from the committed source.

Only files from `src/balance_trees/showcase/site/dist/` enter the deployment,
including `results.html`, `summary.html`, recorded CSV/JSON measurements and SVG graphs.
These are measurements recorded on the local computer; Pages does not rerun them.
The build sets browser-only mode, so GitHub Pages makes no calls to the local
Python API. Relative asset and module URLs support `/balance-trees/`, a renamed
repository, a user site, or a custom domain without editing the source.

## Troubleshooting

- **Configure Pages fails / site not found:** enable GitHub Actions as the Pages
  source in Settings → Pages, then rerun the workflow.
- **Tests fail:** inspect the failed step in Actions. Deployment waits for tests;
  fix the source and push again.
- **404 at the site URL:** verify that the deploy job succeeded and use its exact
  deployment URL, including the repository path. Initial publication can take time.
- **Cannot run the workflow after forking:** enable Actions in the fork and
  configure Pages there. GitHub reports that fork's own deployment URL.

If using GitHub Free, a public repository supports this public Pages setup.
See [GitHub's Pages availability and configuration](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
