"""File explorer for the tower (browse, search, download, upload).

Background threads never touch widgets: they post to `self.q`.
"""
from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk

from core.files import FileEntry, FileError, FileManager, parent_of
from core.i18n import t

from . import theme as T
from .widgets import ConfirmDialog, button, font


def human(n: int) -> str:
    size = float(n)
    units = (t("B"), t("KB"), t("MB"), t("GB"), t("TB"))
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == units[0] else f"{size:.1f} {unit}"
        size /= 1024
    return ""


class FileBrowser(ctk.CTkToplevel):
    def __init__(self, app, fm: FileManager, pool, log):
        super().__init__(app, fg_color=T.BG)
        self.fm, self.pool, self.log = fm, pool, log
        self.title(t("Tower files"))
        self.geometry("980x640")
        self.minsize(760, 480)
        self.q: queue.Queue = queue.Queue()
        self.path = ""
        self.mode = "browse"  # "browse" | "search"
        self.entries: dict[str, FileEntry] = {}
        self._req = 0  # invalidates stale listing answers
        self._busy = False
        self._alive = True
        self._cancel = threading.Event()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)
        self.go(self.fm.start_path)

    # ------------------------------------------------------------------ UI
    def _style_tree(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("RH.Treeview", background=T.SURFACE, fieldbackground=T.SURFACE, foreground=T.TEXT,
                     bordercolor=T.BORDER, rowheight=28, borderwidth=0, font=(T.FONT, 11))
        st.map("RH.Treeview", background=[("selected", "#164e63")], foreground=[("selected", T.TEXT)])
        st.configure("RH.Treeview.Heading", background=T.SURFACE_2, foreground=T.MUTED, relief="flat",
                     font=(T.FONT, 10, "bold"))
        st.map("RH.Treeview.Heading", background=[("active", T.BTN_HOVER)])

    def _build(self):
        self._style_tree()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        nav.columnconfigure(1, weight=1)
        button(nav, "↑", self.up, width=40).grid(row=0, column=0, padx=(0, 6))
        self.path_entry = ctk.CTkEntry(nav, height=34, fg_color=T.SURFACE, border_color=T.BORDER,
                                       font=font(12, mono=True))
        self.path_entry.grid(row=0, column=1, sticky="ew")
        self.path_entry.bind("<Return>", lambda _e: self.go(self.path_entry.get().strip()))
        roots = [t("Drives")] + self.fm.roots
        self.roots_menu = ctk.CTkOptionMenu(nav, values=roots, width=170, height=34, fg_color=T.BTN,
                                            button_color=T.BTN_HOVER, button_hover_color=T.BORDER,
                                            command=self._pick_root, dynamic_resizing=False)
        self.roots_menu.set(t("Shortcuts…"))
        self.roots_menu.grid(row=0, column=2, padx=6)
        button(nav, "⟳", self.refresh, width=40).grid(row=0, column=3)

        srch = ctk.CTkFrame(self, fg_color="transparent")
        srch.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        srch.columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(srch, height=34, fg_color=T.SURFACE, border_color=T.BORDER,
                                         placeholder_text=t("Search this folder and its subfolders (wildcards * ? accepted)"))
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<Return>", lambda _e: self.search())
        button(srch, t("Search"), self.search, "primary", width=110).grid(row=0, column=1, padx=(6, 0))
        self.back_btn = button(srch, t("Close search"), self.refresh, width=140)

        box = ctk.CTkFrame(self, fg_color=T.SURFACE, border_color=T.BORDER, border_width=1, corner_radius=10)
        box.grid(row=2, column=0, sticky="nsew", padx=14, pady=4)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(box, columns=("size", "date"), style="RH.Treeview", selectmode="extended")
        self.tree.heading("#0", text=t("Name"), anchor="w")
        self.tree.heading("size", text=t("Size"), anchor="e")
        self.tree.heading("date", text=t("Modified"), anchor="w")
        self.tree.column("#0", width=520, stretch=True)
        self.tree.column("size", width=100, anchor="e", stretch=False)
        self.tree.column("date", width=140, stretch=False)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(2, 0), pady=2)
        sb.grid(row=0, column=1, sticky="ns", pady=2)
        self.tree.bind("<Double-1>", self._open_selected)
        self.tree.bind("<Return>", self._open_selected)
        self.tree.bind("<BackSpace>", lambda _e: self.up())

        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.grid(row=3, column=0, sticky="ew", padx=14, pady=6)
        self.dl_btn = button(acts, "⬇  " + t("Download"), self.download, "primary")
        self.up_btn = button(acts, "⬆  " + t("Upload files"), self.upload_files)
        self.upd_btn = button(acts, "⬆  " + t("Upload a folder"), self.upload_folder)
        self.mk_btn = button(acts, t("New folder"), self.new_folder)
        for b in (self.dl_btn, self.up_btn, self.upd_btn, self.mk_btn):
            b.pack(side="left", padx=(0, 8))
        button(acts, t("Open my downloads"), self._open_downloads).pack(side="right")

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 14))
        foot.columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(foot, text="", font=font(12), text_color=T.MUTED, anchor="w")
        self.status.grid(row=0, column=0, sticky="ew")
        self.bar = ctk.CTkProgressBar(foot, height=8, fg_color=T.SURFACE_2, progress_color=T.CYAN)
        self.bar.set(0)
        self.cancel_btn = button(foot, t("Cancel"), self._cancel.set, "danger", width=80)

    # ---------------------------------------------------------- navigation
    def _pick_root(self, choice: str):
        self.roots_menu.set(t("Shortcuts…"))
        self.go("" if choice == t("Drives") else choice)

    def up(self):
        if self.mode == "browse":
            self.go(parent_of(self.path))

    def refresh(self):
        self.go(self.path)

    def go(self, path: str):
        self.mode = "browse"
        self.back_btn.grid_forget()
        self._req += 1
        req = self._req
        self._set_status(t("Loading…"))

        def job():
            try:
                self.q.put(("listing", req, path, self.fm.list(path), None))
            except FileError as exc:
                self.q.put(("listing", req, path, None, str(exc)))
            except Exception as exc:  # safety net
                self.q.put(("listing", req, path, None, t("Unexpected error: {exc}", exc=exc)))
        self.pool.submit(job)

    def search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        root = self.path or "C:\\"
        self._req += 1
        req = self._req
        self._set_status(t("Searching for \"{query}\" in {root} (may take a while on a big disk)…", query=query, root=root))

        def job():
            try:
                self.q.put(("search", req, query, self.fm.search(root, query), None))
            except FileError as exc:
                self.q.put(("search", req, query, None, str(exc)))
            except Exception as exc:
                self.q.put(("search", req, query, None, t("Unexpected error: {exc}", exc=exc)))
        self.pool.submit(job)

    def _open_selected(self, _e=None):
        sel = self._selected()
        if len(sel) == 1 and sel[0].is_dir:
            self.go(sel[0].path)
        elif len(sel) == 1:
            self.download()

    def _selected(self) -> list[FileEntry]:
        return [self.entries[i] for i in self.tree.selection() if i in self.entries]

    # ------------------------------------------------------------ transferts
    def download(self):
        sel = self._selected()
        if not sel:
            self._set_status(t("Select at least one file or folder."))
            return
        self._run_transfer(t("Downloading {n} item(s)", n=len(sel)),
                           lambda prog: self.fm.download(sel, prog, self._cancel),
                           lambda res: t("Downloaded to {path}", path=self.fm.download_dir))

    def upload_files(self):
        paths = filedialog.askopenfilenames(parent=self, title=t("Files to upload to {path}", path=self.path or "?"))
        if paths:
            self._prepare_upload([Path(p) for p in paths])

    def upload_folder(self):
        d = filedialog.askdirectory(parent=self, title=t("Folder to upload"))
        if d:
            self._prepare_upload([Path(d)])

    def _prepare_upload(self, locals_: list[Path]):
        if not self.path or self.mode != "browse":
            self._set_status(t("First open a destination folder on the tower (not the drive list)."))
            return
        dest = self.path
        self._set_status(t("Preparing the upload…"))

        def job():
            try:
                plan = self.fm.plan_upload(locals_, dest)
                if not plan:
                    raise FileError(t("Nothing to upload."))
                clashes = [r for lp, r in plan if lp.is_file() and self.fm.exists(r)]
                self.q.put(("confirm_upload", plan, clashes, dest, None))
            except FileError as exc:
                self.q.put(("confirm_upload", None, None, dest, str(exc)))
            except Exception as exc:
                self.q.put(("confirm_upload", None, None, dest, t("Unexpected error: {exc}", exc=exc)))
        self.pool.submit(job)

    def _start_upload(self, plan, dest):
        n = sum(1 for lp, _ in plan if lp.is_file())
        self._run_transfer(t("Uploading {n} file(s) to {dest}", n=n, dest=dest),
                           lambda prog: self.fm.upload(plan, prog, self._cancel),
                           lambda res: t("Uploaded to {dest}", dest=dest), refresh_after=True)

    def _run_transfer(self, label, work, done_msg, refresh_after=False):
        if self._busy:
            self._set_status(t("A transfer is already running."))
            return
        self._busy = True
        self._cancel.clear()
        self._lock_buttons(True)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.cancel_btn.grid(row=0, column=1, rowspan=2, padx=(10, 0))
        self._set_status(label + "…")
        self.log("info", label)
        t0 = time.time()

        def progress(done: int, total: int, name: str):
            self.q.put(("progress", done, total, name, t0))

        def job():
            try:
                res = work(progress)
                self.q.put(("transfer_done", True, done_msg(res), refresh_after))
            except FileError as exc:
                self.q.put(("transfer_done", False, str(exc), refresh_after))
            except Exception as exc:
                self.q.put(("transfer_done", False, t("Unexpected error: {exc}", exc=exc), refresh_after))
        self.pool.submit(job)

    def new_folder(self):
        if not self.path or self.mode != "browse":
            self._set_status(t("First open a folder (not the drive list)."))
            return
        dlg = ctk.CTkInputDialog(text=t("Name of the new folder:"), title=t("New folder"))
        name = (dlg.get_input() or "").strip()
        if not name:
            return

        def job():
            try:
                self.fm.mkdir(self.path, name)
                self.q.put(("mkdir", True, t("Folder created: {name}", name=name)))
            except FileError as exc:
                self.q.put(("mkdir", False, str(exc)))
        self.pool.submit(job)

    def _open_downloads(self):
        self.fm.download_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.fm.download_dir)

    # --------------------------------------------------------------- events
    def _poll(self):
        if not self._alive:
            return
        try:
            for _ in range(60):
                ev = self.q.get_nowait()
                getattr(self, f"_on_{ev[0]}")(*ev[1:])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _fill(self, entries: list[FileEntry], show_path: bool):
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        for i, e in enumerate(entries):
            icon = "📁 " if e.is_dir else "📄 "
            label = icon + (e.path if show_path else e.name)
            date = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.mtime)) if e.mtime else ""
            iid = str(i)
            self.tree.insert("", "end", iid=iid, text=label, values=("" if e.is_dir else human(e.size), date))
            self.entries[iid] = e

    def _on_listing(self, req, path, entries, error):
        if req != self._req:
            return
        if error:
            self._set_status("⚠ " + error, T.RED)
            self.log("err", t("Files: {error}", error=error))
            return
        self.path = path
        self.mode = "browse"
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, path)
        self._fill(entries, show_path=False)
        n_dirs = sum(1 for e in entries if e.is_dir)
        self._set_status(t("{dirs} folder(s), {files} file(s)", dirs=n_dirs, files=len(entries) - n_dirs) if path else t("Tower drives"))

    def _on_search(self, req, query, entries, error):
        if req != self._req:
            return
        if error:
            self._set_status("⚠ " + error, T.RED)
            return
        self.mode = "search"
        self._fill(entries, show_path=True)
        self.back_btn.grid(row=0, column=2, padx=(6, 0))
        cap = t(" (limited to the first 300)") if len(entries) >= 300 else ""
        self._set_status(t("{n} result(s) for \"{query}\"{cap}", n=len(entries), query=query, cap=cap))

    def _on_confirm_upload(self, plan, clashes, dest, error):
        if error:
            self._set_status("⚠ " + error, T.RED)
            return
        if not clashes:
            self._start_upload(plan, dest)
            return
        shown = ", ".join(Path(c.replace("\\", "/")).name for c in clashes[:3])
        more = t(" and {n} more", n=len(clashes) - 3) if len(clashes) > 3 else ""
        ConfirmDialog(self, t("Replace files?"),
                      t("{n} file(s) already exist on the tower ({shown}{more}). They will be overwritten.",
                        n=len(clashes), shown=shown, more=more),
                      t("Replace"), lambda: self._start_upload(plan, dest))

    def _on_progress(self, done, total, name, t0):
        frac = done / total if total else 1
        self.bar.set(frac)
        speed = done / max(time.time() - t0, 0.1)
        eta = t(" · ~{s} s left", s=int((total - done) / speed)) if speed > 0 and done < total else ""
        self._set_status(f"{name}  {human(done)} / {human(total)}  ({human(int(speed))}/s){eta}")

    def _on_transfer_done(self, ok, msg, refresh_after):
        self._busy = False
        self._lock_buttons(False)
        self.bar.grid_forget()
        self.cancel_btn.grid_forget()
        self._set_status(("✔ " if ok else "⚠ ") + msg, T.GREEN if ok else T.RED)
        self.log("ok" if ok else "err", msg)
        if refresh_after and self.mode == "browse":
            self.refresh()

    def _on_mkdir(self, ok, msg):
        self._set_status(("✔ " if ok else "⚠ ") + msg, T.GREEN if ok else T.RED)
        if ok:
            self.refresh()

    # -------------------------------------------------------------- helpers
    def _set_status(self, text: str, color: str = T.MUTED):
        self.status.configure(text=text, text_color=color)

    def _lock_buttons(self, busy: bool):
        for b in (self.dl_btn, self.up_btn, self.upd_btn, self.mk_btn):
            b.configure(state="disabled" if busy else "normal")

    def _close(self):
        self._alive = False
        self._cancel.set()
        self.destroy()
