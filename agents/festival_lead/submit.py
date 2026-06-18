"""
提出スクリプト（agents/festival_lead/ から実行）
  python submit.py

実行内容:
  1. 現在の main.py を v{n}_agent.py としてアーカイブ（比較用）
  2. submission/ に main.py と deck.csv を同期
  3. submissions/v{n}_festival_lead.tar.gz を作成
  4. プロジェクトルートに submission.tar.gz を出力（Kaggle アップロード用）

提出後の比較:
  cd ../..
  python simulate.py festival_lead --compare
"""
import os
import sys
import shutil
import glob
import tarfile
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
os.chdir(_HERE)

# --- 次のバージョン番号を決定 ---
existing_nums = []
for f in glob.glob(os.path.join(_HERE, "v*_agent.py")):
    m = re.match(r"v(\d+)_agent\.py", os.path.basename(f))
    if m:
        existing_nums.append(int(m.group(1)))
next_v = max(existing_nums, default=0) + 1
archive_name = f"v{next_v}_agent.py"

# 確認
print(f"Archive as : {archive_name}")
print(f"Tar output : submissions/v{next_v}_festival_lead.tar.gz")
answer = input("Proceed? [y/N] ").strip().lower()
if answer != "y":
    print("Cancelled.")
    sys.exit(0)

# --- 1. main.py → v{n}_agent.py ---
shutil.copy("main.py", archive_name)
print(f"  [1] Archived -> {archive_name}")

# --- 2. submission/ に同期 ---
submission_dir = os.path.join(_ROOT, "submission")
shutil.copy("main.py",  os.path.join(submission_dir, "main.py"))
shutil.copy("deck.csv", os.path.join(submission_dir, "deck.csv"))
print(f"  [2] Synced  -> submission/main.py, submission/deck.csv")

# --- 3. tar.gz 作成 ---
submissions_dir = os.path.join(_ROOT, "submissions")
os.makedirs(submissions_dir, exist_ok=True)
tar_path = os.path.join(submissions_dir, f"v{next_v}_festival_lead.tar.gz")

with tarfile.open(tar_path, "w:gz") as tar:
    for entry in os.listdir(submission_dir):
        full = os.path.join(submission_dir, entry)
        tar.add(full, arcname=entry)

print(f"  [3] Created -> submissions/v{next_v}_festival_lead.tar.gz")

# --- 4. ルートに submission.tar.gz を出力 ---
root_tar = os.path.join(_ROOT, "submission.tar.gz")
shutil.copy(tar_path, root_tar)
print(f"  [4] Created -> submission.tar.gz  (upload this to Kaggle)")
