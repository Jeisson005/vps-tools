---
name: workspace-files
description: "Autonomously handle attached files and scripts across all channels (Open WebUI, Telegram, WhatsApp), materialize code into the shared workspace, and execute, modify, or transfer them on the server."
version: 1.0.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [workspace, files, uploads, execution, scripts, scp, transfers, webui, telegram, whatsapp, documents]
    category: tools
    related_skills: [browser-automation, desktop-gui-control]
---

# Universal Workspace & File Lifecycle Skill

Manages the autonomous lifecycle of files, attached scripts, and documents received across **Open WebUI**, **Telegram**, **WhatsApp**, or direct API requests.

---

## 📂 Primary Workspace & Storage Locations

Always use these standardized directories when reading, saving, or executing files:

1. **Shared Multi-Channel Workspace:**
   `~/vps-tools/open-webui/data/workspace/`
   * *Primary working folder shared between the host VPS, terminal tools, and the Open WebUI container.*
2. **Open WebUI Uploads Repository:**
   `~/vps-tools/open-webui/data/open-webui/uploads/`
   * *Location where uploaded media, binary datasets, and documents from the web interface reside.*
3. **Telegram & WhatsApp Documents Cache:**
   `~/.hermes/cache/document_cache/`
   * *Location where incoming files received via messaging bots are cached.*

---

## ⚙️ Autonomous File Handling Protocols

### 1. 🚀 Materialization & Code Execution
When the user sends code or attaches a script (`.py`, `.sh`, `.js`, `.ts`, `.sql`, `.yml`, `.json`) and asks to **execute, test, compile, or run** it:

1. **Identify the File:** Extract the filename from the attachment header (e.g., `### Attached File: script.py`) or infer a logical name if none was given.
2. **Materialize to Disk:** Write the complete code content into the shared workspace:
   ```bash
   mkdir -p ~/vps-tools/open-webui/data/workspace
   # Write content to ~/vps-tools/open-webui/data/workspace/<filename>
   ```
3. **Set Permissions:** If it is an executable script (`.sh`, `.py`, `.bin`), grant executable permissions:
   ```bash
   chmod +x ~/vps-tools/open-webui/data/workspace/<filename>
   ```
4. **Execute & Observe:** Run the script using the appropriate runtime from the workspace directory and return the execution output clearly to the user:
   ```bash
   cd ~/vps-tools/open-webui/data/workspace && python3 <filename>
   ```

---

### 2. 📤 Remote Transfers (SCP / SSH / Rsync)
When the user asks to **upload or transfer an attached file to another server**:

1. Write the file into `~/vps-tools/open-webui/data/workspace/<filename>`.
2. Execute the transfer command (e.g., `scp`, `rsync`):
   ```bash
   scp ~/vps-tools/open-webui/data/workspace/<filename> user@destination:/target/path/
   ```
3. Confirm the successful transfer to the user.

---

### 3. 💾 Output File Creation & Persistence
When you generate a new file, report, dataset, or modified script for the user:

1. Always save the resulting file in the shared workspace:
   `~/vps-tools/open-webui/data/workspace/<result_file>`
2. Notify the user of the exact filename and location so they can access or download it immediately.

---

### 4. 🔍 Locating Uploaded Binary Files & Datasets
If the user references an uploaded file (such as a PDF, ZIP, or SQLite database) without pasting its raw text:

1. Look in `~/vps-tools/open-webui/data/workspace/` and `~/vps-tools/open-webui/data/open-webui/uploads/`:
   ```bash
   find ~/vps-tools/open-webui/data/ -name "*<filename>*" 2>/dev/null
   ```
2. Process the located file according to the user's instructions.
