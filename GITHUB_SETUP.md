# Push this project to GitHub

Git is initialized on branch **`main`** with an initial commit. **`.env` is not tracked** (see `.gitignore`).

## One-time: sign in to GitHub

Install [GitHub CLI](https://cli.github.com/) or use the copy already downloaded during setup, then:

```powershell
cd "d:\PM\Discovery Engine"
gh auth login
```

Choose: GitHub.com → HTTPS → Login with a web browser.

## Create repo and upload

```powershell
cd "d:\PM\Discovery Engine"
gh repo create discovery-engine --private --source=. --remote=origin --push
```

Use a different name if `discovery-engine` is taken:

```powershell
gh repo create google-photos-discovery-engine --private --source=. --remote=origin --push
```

Your repo URL will be printed (e.g. `https://github.com/YOUR_USER/discovery-engine`).

## SSH error: `Permission denied (publickey)`

If you added the remote as `git@github.com:USER/REPO.git`, Git uses SSH keys. Either [add an SSH key to GitHub](https://docs.github.com/en/authentication/connecting-to-github-with-ssh) **or** switch to HTTPS (recommended on Windows):

```powershell
cd "d:\PM\Discovery Engine"
git remote set-url origin https://github.com/YOUR_USER/REPO.git
git push -u origin main
```

Git Credential Manager will open a browser sign-in for GitHub.

## Manual alternative (no gh)

1. On https://github.com/new create an empty repo (no README).
2. Then:

```powershell
cd "d:\PM\Discovery Engine"
git remote add origin https://github.com/YOUR_USER/REPO.git
git push -u origin main
```

## VPS deploy after push

On the VPS:

```bash
cd ~/projects
git clone https://github.com/YOUR_USER/discovery-engine.git
cd discovery-engine
# follow DEPLOY.md
```
