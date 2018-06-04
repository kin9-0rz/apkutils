# coding: utf-8
# Author: codeskyblue 2018-06-04

import tkinter as tk
import winreg
import ctypes
import sys
import argparse
import os
import apkutils


def _bind_apk_right_menu():
    # Run ad administrator
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, __file__ + " --bind", None, 0)
        return

    # Mouse Right menu "Parse APK File"
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root_key:
        with winreg.CreateKeyEx(root_key, r"Apkutils.GUI\shell\Parse APK File\command", 0, winreg.KEY_WRITE) as key:
            winreg.SetValue(key, "", 1, " ".join(
                [sys.executable.replace("python.exe", "pythonw.exe"), os.path.abspath(__file__), "--file",  "\"%1\""]))

    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "", 0, winreg.KEY_WRITE) as key:
        with winreg.CreateKeyEx(key, ".apk", 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0,
                              winreg.REG_SZ, "Apkutils.GUI")

    print("Binded")


def _unbind_reg():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, __file__ + "  --unbind", None, 0)
        return

    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r".apk", 0, winreg.KEY_ALL_ACCESS) as key:
        winreg.DeleteValue(key, "")
        # winreg.DeleteValue(key, "Apkutils.back_up")

    # Delete recursively
    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT,
                     r"Apkutils.GUI\\shell\\Parse APK File\\command")
    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT,
                     r"Apkutils.GUI\\shell\\Parse APK File")
    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT,
                     r"Apkutils.GUI\\shell")
    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT,
                     r"Apkutils.GUI")


class TKList(object):
    def __init__(self):
        self._row = 0

    def add_row(self, *widgets):
        for (column, widget) in enumerate(widgets):
            if isinstance(widget, str):
                text = tk.Text(height=1)
                text.insert(tk.INSERT, widget)

                # ref: https://tkdocs.com/tutorial/text.html
                text.bind("<FocusIn>", lambda event: text.tag_add(
                    tk.SEL, "1.0", "1.end"))
                widget = text
            widget.grid(row=self._row, column=column)
        self._row += 1


def main(path):
    root = tk.Tk()

    if path:
        apk = apkutils.APK(path)
        mf = apk.manifest
        grid = TKList()
        grid.add_row(tk.Label(text="Filename"), os.path.basename(path))
        grid.add_row(tk.Label(text="Package Name"), mf.package_name)
        grid.add_row(tk.Label(text="Main Activity"), mf.main_activity)
        grid.add_row(tk.Label(text="Version Name"), mf.version_name)
        grid.add_row(tk.Label(text="Version Code"), mf.version_code)
    else:
        tk.Button(root, text="Bind to *.apk Right MENU",
                  command=_bind_apk_right_menu).pack(padx=10, pady=5)
        tk.Button(root, text="Unbind",
                  command=_unbind_reg).pack(padx=10, pady=5, side=tk.LEFT)

    tk._default_root.title("APK Parser")
    tk.mainloop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="parsed file")
    parser.add_argument("--bind", action="store_true",
                        help="Bind right-click menu")
    parser.add_argument("--unbind", action="store_true",
                        help="Unbind right-click menu")
    args = parser.parse_args()

    if args.bind:
        _bind_apk_right_menu()
    elif args.unbind:
        _unbind_reg()
    else:
        main(args.file)
