# Automatic Commenter

Automates posting comments on Facebook (and eventually other platforms). You give it a list of posts and a list of comments, and it opens Chrome, logs into your account, and posts one comment on each post automatically.

---

## Getting Started (for Dad)

### Step 1: Download the project (first time only)

1. Open VS Code
2. Open a terminal: press `` Ctrl+` `` (backtick key, top-left of keyboard next to the 1 key)
3. Navigate to where you want to put the project. For example, to put it on your Desktop:
   ```
   cd Desktop
   ```
4. Download the project:
   ```
   git clone https://github.com/mckinlde/Automatic-Commenter.git
   ```
5. Open the project folder: File → Open Folder → navigate to Desktop → select `Automatic-Commenter` → click "Select Folder"

**Next time** you open VS Code, you can skip this step — just do File → Open Folder and pick the `Automatic-Commenter` folder wherever you put it. To get the latest updates, open the terminal and run:
```
git pull
```

### Step 2: Set up Python (first time only)

Open a terminal in VS Code (`` Ctrl+` ``) and run these commands one at a time:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

You should see the terminal prompt change to show `(.venv)` at the beginning. That means it worked.

### Step 3: Activate the virtual environment (every time you open the project)

Every time you open VS Code fresh, open a terminal (`` Ctrl+` ``) and run:

```
.venv\Scripts\activate
```

You'll know it's working when you see `(.venv)` in your terminal prompt.

### Step 4: Edit your post list

Open the file `test_data/posts.csv` in VS Code. It looks like this:

```
index,url,platform
0,https://www.facebook.com/groups/123456789/posts/987654321,facebook
1,https://www.facebook.com/groups/123456789/posts/987654322,facebook
```

Replace the URLs with the actual Facebook post URLs you want to comment on. The `index` column should be sequential numbers starting from 0. Keep `platform` as `facebook`.

To get a post URL: right-click the post's timestamp on Facebook → Copy Link.

### Step 5: Edit your comments

Open `test_data/comments.csv`. It looks like this:

```
comment_text,comment_index
This is a great initiative! Thank you for sharing.,0
I appreciate the work being done here. Keep it up!,1
```

Replace with your actual comments. The `comment_index` column should be sequential numbers starting from 0. Each post gets a different comment (they cycle through the list).

### Step 6: Run it

```
python app_ac.py --test
```

Here's what happens:
1. The AutoCommenter GUI opens with "[TEST MODE]" in the title bar
2. Select **Facebook** from the platform options
3. Click **Start**
4. Chrome opens and goes to the Facebook login page
5. **You log in yourself** — type your email and password, handle any CAPTCHAs or verification prompts, do whatever Facebook asks until you see your News Feed
6. Click the **"I'm Logged In"** button in the AutoCommenter window
7. The tool starts visiting each post and posting comments automatically

You can watch Chrome doing its thing. Click **Stop** if you need to halt it.

### Step 7: If you want to start over

If you want to re-comment on posts you already did, delete the cursor file:
```
del %LOCALAPPDATA%\AutoCommenter\cursors.json
```
Then run it again.

---

## Common Issues

**"git is not recognized"** — Git isn't installed. Download it from https://git-scm.com/download/win — use all the default options during install, then restart VS Code.

**"python is not recognized"** — Python isn't installed or isn't in your PATH. Download it from https://python.org and check "Add to PATH" during install.

**"(.venv) doesn't appear"** — You need to run `.venv\Scripts\activate` first.

**Chrome doesn't open** — Make sure Google Chrome is installed. The tool downloads the right driver automatically, but Chrome itself needs to be on your machine.

**It skips posts / says "comment field not found"** — Facebook changes their page layout sometimes. Let me know and I'll update the selectors.

**It stops mid-way** — Your progress is saved. Just run `python test_runner.py` again and it picks up where it left off.

---

## Full Command Reference

```bash
# Normal GUI mode (requires license + Campaign Server):
python app_ac.py

# Test mode GUI (local CSVs, no license, no server):
python app_ac.py --test
# Note: --test is only available when running from source.
# It is disabled in the packaged .exe build.
```

---

## How It Works (Technical)

Architecture: PySide6 GUI → QThread worker → Selenium browser automation → local JSON persistence.

### Workflow

1. Loads target posts from CSV (or Campaign Server in production mode)
2. Loads comment pool from CSV (or Campaign Server)
3. Opens Chrome in headed mode (you can see and interact with it)
4. Navigates to the login page — **you log in manually** and press Enter when done
5. For each unprocessed post: navigates, finds the comment box, types the comment, submits
6. Saves a cursor after each success so it can resume on restart
7. Waits 5 seconds between posts to avoid rate limiting

### Project Structure

```
├── app_ac.py                  # Entry point (python app_ac.py for GUI, --test for test mode)
├── local_campaign_client.py   # Reads posts/comments from CSV (test mode data source)
├── gui_ac.py                  # PySide6 GUI (both normal and test mode)
├── worker.py                  # Background thread for commenting workflow
├── browser_engine.py          # Selenium Chrome control + robust click handling
├── campaign_client.py         # Campaign Server HTTP client (production mode)
├── cursor_manager.py          # Tracks which posts have been commented (atomic file writes)
├── platform_strategies.py     # Facebook/Twitter/Instagram/TikTok DOM selectors
├── models_ac.py               # Data structures
├── config_ac.py               # App constants and local storage
├── license_manager.py         # Stripe-based license verification
├── test_data/
│   ├── posts.csv              # Your target posts (edit this)
│   └── comments.csv           # Your comment pool (edit this)
├── build_ac.bat/.ps1          # Package as standalone .exe
├── server/                    # Backend server code
└── test_*.py                  # 152 automated tests
```

### Error Handling

- Page won't load (30s timeout) → skips that post, continues
- Can't find comment box (15s) → skips, continues
- Comment submission fails → waits 5s, retries once, then skips
- Rate limited by Facebook → pauses (60s or whatever Facebook says), then continues
- Session expires → pauses, asks you to re-login, resumes from where it stopped

### Automated Test Suite

```bash
python -m pytest          # Run all 152 tests
python -m pytest -v       # Verbose output
```

## Building Standalone Executable

```bash
.\build_ac.bat     # or build_ac.ps1
```

Produces `dist\AutoCommenter\AutoCommenter.exe` — no Python install needed to run it.

## License

Proprietary. Subscription required via Stripe for production GUI mode. Test mode (CLI) does not require a license.
