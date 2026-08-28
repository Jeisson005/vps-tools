---
name: webui-workspace
description: "Autonomously handle files and scripts attached via Open WebUI, read from shared storage, execute scripts, and register generated files for instant native download in chat."
version: 1.2.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [webui, open-webui, workspace, uploads, execution, scripts, scp, transfers, files, downloads]
    category: tools
    related_skills: [browser-automation]
---

# Open WebUI Workspace & File Lifecycle Skill

Dedicated skill for handling files, attached scripts, and datasets submitted through the **Open WebUI** interface (`https://chat.jeisson.top`).

---

## 📂 Open WebUI Shared Storage Locations

All files interacting with the Open WebUI container reside in these dedicated server paths:

1. **Shared Workspace Directory:**
   `~/vps-tools/open-webui/data/workspace/`
   * *Mounted to `/workspace` inside Open WebUI. Working directory for scripts, executions, and file edits.*
2. **Open WebUI Uploads Repository:**
   `~/vps-tools/open-webui/data/open-webui/uploads/`
   * *Where Open WebUI stores all raw uploaded files, binary assets, and document attachments.*

---

## ⚙️ Open WebUI File Handling Protocols

### 1. 🚀 Code Execution & Script Materialization
When a user attaches code in Open WebUI (indicated by headers like `### Attached File: <filename>` or embedded code blocks) and asks to **execute, run, test, or compile** it:

1. **Identify the File Name:** Extract the filename from the Open WebUI attachment header or infer a logical name.
2. **Write to Shared Workspace:** Save the complete code to:
   `~/vps-tools/open-webui/data/workspace/<filename>`
3. **Set Permissions:** If it is a script (`.sh`, `.py`, `.js`), apply executable permissions:
   ```bash
   chmod +x ~/vps-tools/open-webui/data/workspace/<filename>
   ```
4. **Execute on Host:** Run the script from the workspace directory and report the output in the Open WebUI chat:
   ```bash
   cd ~/vps-tools/open-webui/data/workspace && ./<filename>
   ```

---

### 2. 📥 Native File Delivery & Download Cards
When you generate a new file, report, processed image, or modified document (e.g. PDF, CSV, Excel, ZIP) for the user in Open WebUI:

1. **Save to Workspace:** Save the file into `~/vps-tools/open-webui/data/workspace/<filename>`.
2. **Register File in Open WebUI:** Run the bridge command:
   ```bash
   webui-file-upload ~/vps-tools/open-webui/data/workspace/<filename>
   ```
3. **Provide Download Card:** Extract the returned download markdown link (e.g. `[📄 <filename>](/api/v1/files/<file_id>/content)`) and present it clearly to the user in your message:
   ```markdown
   Aquí tienes tu archivo listo para descargar o previsualizar:
   [📄 <filename>](/api/v1/files/<file_id>/content)
   ```
   *This generates an authenticated, native Open WebUI file card that allows the user to preview or download the file with 1 click.*

---

### 3. 📤 Remote Transfers from WebUI
When the user asks to **transfer an attached file to another server**:

1. Save the file in `~/vps-tools/open-webui/data/workspace/<filename>`.
2. Transfer it using `scp` or `rsync`:
   ```bash
   scp ~/vps-tools/open-webui/data/workspace/<filename> user@destination:/target/path/
   ```
3. Confirm the transfer to the user.

---

### 4. 🔍 Locating Raw Uploads
If the user references an uploaded binary file, database, or document stored in Open WebUI:

1. Search directly inside the Open WebUI uploads repository:
   ```bash
   find ~/vps-tools/open-webui/data/open-webui/uploads/ -name "*<filename>*" 2>/dev/null
   ```
2. Process or inspect the located file as requested.
