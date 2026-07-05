# 433 West 34th Street — Alteration App Setup Guide

This guide walks you through everything needed to get the app running.
You'll need about 45–60 minutes the first time.

---

## What You'll Set Up

1. `apps@433w34.com` email address (Google Workspace)
2. Google Cloud project + API access
3. Anthropic API key (for the AI review)
4. Google Sheet and Drive folder for storing applications
5. The app running locally, then deployed online

---

## Step 1 — Create apps@433w34.com

1. Go to [admin.google.com](https://admin.google.com) and sign in as your workspace admin
2. Go to **Directory → Users → Add new user**
3. Create a user with the email `apps@433w34.com`
4. Set a strong password and save it somewhere safe
5. You don't need to actively monitor this inbox — the app uses it as a send-from address

---

## Step 2 — Set Up a Google Cloud Project

This gives the app permission to use Gmail, Drive, and Sheets on your behalf.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project → New Project**
3. Name it `433 Alterations App` and click **Create**
4. Make sure your new project is selected in the top bar

### Enable the APIs

5. Go to **APIs & Services → Library**
6. Search for and enable each of these (click the API name, then click **Enable**):
   - **Gmail API**
   - **Google Drive API**
   - **Google Sheets API**
   - **Google OAuth2 API** (also called "Google Identity")

### Create OAuth Credentials

7. Go to **APIs & Services → OAuth consent screen**
8. Choose **Internal** (since this is for your organization only) → Click **Create**
9. Fill in:
   - App name: `433 Alterations App`
   - User support email: `board@433w34.com`
   - Developer contact: `board@433w34.com`
   - Click **Save and Continue** through the remaining screens
10. Go to **APIs & Services → Credentials → Create Credentials → OAuth Client ID**
11. Application type: **Web application**
12. Name: `433 Alterations App`
13. Under **Authorized redirect URIs**, add:
    - `http://localhost:5000/auth/callback` (for local testing)
    - `https://your-app-name.onrender.com/auth/callback` (you'll fill this in after Step 6)
14. Click **Create** — a popup shows your **Client ID** and **Client Secret**. Copy both.

---

## Step 3 — Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com) and sign up / log in
2. Go to **API Keys → Create Key**
3. Name it `433 Alterations App` and copy the key (starts with `sk-ant-`)
4. This powers the AI document review. Usage costs roughly $0.01–0.05 per application reviewed — negligible.

---

## Step 4 — Create the Google Sheet and Drive Folder

### Google Sheet (application tracker)

1. Go to [sheets.google.com](https://sheets.google.com) and create a new blank spreadsheet
2. Name it `433 Alteration Applications`
3. Copy the Sheet ID from the URL — it's the long string between `/d/` and `/edit`:
   `https://docs.google.com/spreadsheets/d/**THIS-PART**/edit`

### Google Drive Folder (document storage)

1. Go to [drive.google.com](https://drive.google.com) and create a new folder
2. Name it `433 Alteration Applications`
3. Open the folder and copy the folder ID from the URL — it's the long string at the end:
   `https://drive.google.com/drive/folders/**THIS-PART**`

---

## Step 5 — Configure the App

1. In the project folder (`Test Code - Alteration App`), find the file called `.env.example`
2. Make a copy of it and rename the copy to `.env` (just `.env`, no "example")
3. Open `.env` in a text editor and fill in all the values:

```
ANTHROPIC_API_KEY=sk-ant-...          ← from Step 3
GOOGLE_CLIENT_ID=...                  ← from Step 2
GOOGLE_CLIENT_SECRET=...              ← from Step 2
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback
GOOGLE_SHEET_ID=...                   ← from Step 4
GOOGLE_DRIVE_FOLDER_ID=...            ← from Step 4
SECRET_KEY=pick-any-long-random-string-here-at-least-32-characters
BOARD_EMAIL=board@433w34.com
ALTERATIONS_EMAIL=apps@433w34.com
EDDIE_EMAIL=rodriguezeddie374@gmail.com
ORSID_CC_EMAILS=cmcgrath@orsidny.com,jdevall@orsidny.com
CAPOBIANCO_EMAIL=tom.sr@capobiancogroup.com
MELONE_EMAILS=jeremy@melonearchitects.com,nick@melonearchitects.com
BUILDING_NAME=433 West 34th Street Owners Corp.
```

---

## Step 6 — Run the App Locally (First Time)

Open the **Terminal** app on your Mac (search for it in Spotlight).

```bash
# Navigate to the project folder
cd ~/Library/CloudStorage/Dropbox/Mac/Desktop/Test\ Code\ -\ Alteration\ App

# Install Python dependencies (only needed once)
pip3 install -r requirements.txt

# Start the app
python3 app.py
```

You should see something like:
```
* Running on http://127.0.0.1:5000
```

Open your browser and go to `http://localhost:5000` — you should see the portal homepage.

### Authorize Google Access (One-Time)

1. Go to `http://localhost:5000/auth/login`
2. Sign in with `board@433w34.com`
3. Grant the permissions requested
4. You'll be redirected to the admin dashboard

This creates a `token.json` file in the project folder. **Keep this file safe** —
it allows the app to send emails and save files on your behalf. Never share it.

**Every time the app restarts, it uses this saved token automatically.**
You only need to log in again if the token expires (roughly every 6 months).

---

## Step 7 — Deploy Online (So Shareholders Can Access It)

The app needs to be hosted somewhere so shareholders can submit applications.
[Render.com](https://render.com) offers a free tier that works well.

1. Create an account at [render.com](https://render.com)
2. The easiest deploy path requires putting the project on GitHub first.
   If you'd like help with this step, just ask — it takes about 10 minutes.
3. Once deployed, you'll get a URL like `https://433-alterations.onrender.com`
4. Go back to Google Cloud Console → Credentials → edit your OAuth client
   and add `https://433-alterations.onrender.com/auth/callback` to the redirect URIs
5. Update `GOOGLE_REDIRECT_URI` in your environment settings on Render to match

---

## Day-to-Day Operation

**To check for new applications:** Go to `https://your-app-url/admin` and log in.

**To assign an architect:** Click into the application → select Melone or Capobianco → click Assign.
The app sends the package to the architect automatically.

**To approve an application:** Click **Approve & Notify All Parties** on the application page.
This sends emails to the shareholder, GC, Eddie, and Orsid in one click.

**To see all applications as a spreadsheet:** Open the Google Sheet you created in Step 4.
Every submission is logged there in real time.

**If the app is down:** All your data is safe in Google Sheets and Drive.
The app just reads from those — it doesn't store anything on its own servers.

---

## Troubleshooting

**"No Google credentials available"** — Go to `/auth/login` and log in as `board@433w34.com`.

**Emails not sending** — Make sure Gmail API is enabled in Google Cloud Console
and that `token.json` was created by logging in (Step 6 above).

**"Application not found" on status page** — The shareholder may have entered their ID incorrectly.
IDs are case-sensitive and look like `ALT-202506-A1B2C`.

**Drive upload errors** — Check that `GOOGLE_DRIVE_FOLDER_ID` in `.env` matches your folder's URL.

---

## Contact

For help with the app itself, open a conversation with Claude Code.
