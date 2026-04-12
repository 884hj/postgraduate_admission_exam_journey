# postgraduate_admission_exam_journey
 西综306

## GitHub Pages

This repository includes a minimal Pages site at `index.html` with a background image and readable text overlay.

### Enable

1. Push the repository to GitHub.
2. Open repository `Settings` -> `Pages`.
3. In `Build and deployment`, choose `Deploy from a branch`.
4. Select branch `main` and folder `/ (root)`.
5. Save and wait for deployment.

After deployment, visit:

`https://<your-username>.github.io/<your-repository-name>/`

### Switch Weekly Background

To change background per week, update one line in `index.html`:

`<body style="--week-bg: url('./周记/sources/第一周/your-image.png'); --overlay-opacity: 0.34;">`

- `--week-bg` is the image path for the current week.
- `--overlay-opacity` controls readability. Larger value means darker overlay and clearer text.
