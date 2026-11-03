#!/usr/bin/env python3
"""Copy reviewed frontend sources into the installable package; no local data."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
dest=root/'reachy_follow_me'/'web'
dest.mkdir(parents=True,exist_ok=True)
for name in ['index.html','lab.js','lab.css','control-core.js','vision.js']:
 text=(root/'web'/name).read_text()
 if name=='index.html':text=text.replace('<head>','<head><base href="/static/">')
 (dest/name).write_text(text)
shutil.copyfile(root/'assets-manifest.json',root/'reachy_follow_me'/'assets-manifest.json')
print('App frontend synchronized (no camera/model/personal data).')
