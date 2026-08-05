# 433 West 34th Street — Alteration Portal

An AI-assisted web app that handles co-op alteration applications from submission through board approval.

**Live app:** https://four33-alteration-app.onrender.com

---

## The problem

The building's managing agent previously handled alteration review for ~$1,000 per application with no shareholder-facing status tracking and slow turnaround. This app replaces that service entirely — shareholders submit directly, documents go to Drive automatically, and the board manages review from a private admin panel without routing everything through the managing agent.

---

## What it does

- **Intake form** — shareholders submit project details, all required documents, and contractor information in one step
- **AI document review** — Claude checks the submission for missing documents, riser risk, and scope flags before the board sees it
- **Status tracking** — shareholders check progress at `/status` using their application ID, without logging in
- **Admin panel** — board assigns the reviewing engineer, tracks status, and sends approval notifications in one click
- **Email routing** — outbound emails (receipt, architect package, approval with next steps) sent automatically via Gmail API
- **Drive storage** — a Google Drive folder is created per application and all uploaded documents are filed there automatically

---

## How it works

Flask app hosted on Render, using Google Sheets as the application database, Google Drive for document storage, and Gmail API for outbound email. Claude (Anthropic API) reviews each submission at intake and will generate board voting summaries once that feature is built. All operational config (contacts, engineer list, fee billing) is editable from the admin settings panel without a redeploy.

**Stack:** Python / Flask · Google Sheets, Drive, Gmail APIs · Anthropic Claude API · Render (Starter)

---

## Setup

See [SETUP.md](SETUP.md) for the full walkthrough (~45 minutes first time). You'll need a Google Cloud project with Gmail/Drive/Sheets APIs enabled, an Anthropic API key, and a Render account.

For architecture decisions, design principles, and operational notes, see [CONTEXT.md](CONTEXT.md).

---

## Status

Live and handling real applications. Board voting (magic-link per member, 4/7 threshold, auto-alert on threshold) is designed and next in the build queue.
