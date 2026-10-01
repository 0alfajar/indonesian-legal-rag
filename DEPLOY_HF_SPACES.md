# Deploy to Hugging Face Spaces

Step-by-step guide to deploy Legal Atlas to Hugging Face Spaces.

## Prerequisites

1. GitHub account
2. Hugging Face account (free: hf.co/join)
3. Git installed locally

## Step 1: Push to GitHub

If you haven't already:

```bash
# Initialize git (if not done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/yourusername/legal-atlas.git

# Push
git push -u origin main
```

## Step 2: Create Hugging Face Space

1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Fill in details:
   - Space name: `legal-atlas`
   - License: `MIT`
   - SDK: `Docker`
   - Hardware: `CPU basic` (free)
4. Click "Create Space"

## Step 3: Connect GitHub Repository

### Option A: Direct Push to HF

1. Clone the Space repository:
   ```bash
   git clone https://huggingface.co/spaces/yourusername/legal-atlas
   cd legal-atlas
   ```

2. Add your project files:
   ```bash
   cp -r /path/to/your/project/* .
   ```

3. Rename README_HF.md to README.md:
   ```bash
   mv README_HF.md README.md
   ```

4. Commit and push:
   ```bash
   git add .
   git commit -m "Deploy Legal Atlas"
   git push
   ```

### Option B: Sync from GitHub (Easier)

1. In your HF Space settings, go to "Files and versions"
2. Add a `.github/workflows/sync.yml` to auto-sync from GitHub
3. Or manually copy files from GitHub to HF each update

## Step 4: Configure Environment Variables (Optional)

For LLM answer generation:

1. Go to Space Settings
2. Click "Variables and secrets"
3. Add secret:
   - Name: `GEMINI_API_KEY`
   - Value: your API key from https://ai.google.dev/

Without this, the system runs in search-only mode.

## Step 5: Wait for Build

1. HF will build the Docker image (5-10 minutes first time)
2. Watch build logs in the Space UI
3. Once "Running", your app is live

## Step 6: Test Deployment

1. Open your Space URL: `https://huggingface.co/spaces/yourusername/legal-atlas`
2. Try a search query in Indonesian
3. Check citations and PDF links work
4. Test document filtering

## Custom Domain (Optional)

1. Go to Space Settings
2. Add custom domain (requires DNS configuration)
3. Format: `legal-atlas.yourdomain.com`

## Embedding in Your Portfolio

Add to your website:

```html
<iframe
  src="https://huggingface.co/spaces/yourusername/legal-atlas"
  width="100%"
  height="800px"
  frameborder="0"
></iframe>
```

## Troubleshooting

### Build fails

Check Dockerfile syntax and dependencies in requirements.txt

### Out of memory

- Reduce batch size in indexing
- Use smaller embedding model (requires code change)
- Upgrade to paid tier for more RAM

### App not loading

- Check port is 7860 in server command
- Verify data files are included
- Check logs in Space UI

### Embeddings not found

Data files should be in repository. If too large:
- Use Git LFS for large files
- Or regenerate on first run (slower)

## Updating the Deployment

```bash
# Make changes locally
git add .
git commit -m "Update: description"

# Push to GitHub
git push origin main

# Push to HF (if using Option A)
git push hf main
```

## Monitoring

- View analytics in Space UI
- Check error logs
- Monitor API usage (if using Gemini)

## Costs

- HF Spaces: Free for CPU basic
- Gemini API: Pay per token (set spending limits)
- Total: $0-5/month depending on usage

## Support

- HF Spaces docs: https://huggingface.co/docs/hub/spaces
- Issues: Open on GitHub repository
- Community: HF Discord or forums
