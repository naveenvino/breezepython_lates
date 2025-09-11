"""
Test Navigation - Verify all links in index.html point to existing files
"""
import os
import re
from pathlib import Path

def test_navigation():
    """Test all navigation links in index.html"""
    base_dir = Path(r"C:\Users\E1791\Kitepy\breezepython\ui")
    index_file = base_dir / "index.html"
    
    if not index_file.exists():
        print("[ERROR] index.html not found!")
        return False
    
    with open(index_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all data-page references
    pattern = r'data-page="([^"]+)"'
    pages = re.findall(pattern, content)
    
    print(f"\n[INFO] Found {len(pages)} navigation links")
    print("-" * 60)
    
    missing_files = []
    found_files = []
    
    for page in pages:
        file_path = base_dir / page
        if file_path.exists():
            found_files.append(page)
            print(f"[OK] {page}")
        else:
            missing_files.append(page)
            print(f"[MISSING] {page}")
    
    print("-" * 60)
    print(f"\nResults:")
    print(f"  Found: {len(found_files)}/{len(pages)}")
    print(f"  Missing: {len(missing_files)}/{len(pages)}")
    
    if missing_files:
        print(f"\nMissing files:")
        for file in missing_files:
            print(f"  - {file}")
    
    return len(missing_files) == 0

if __name__ == "__main__":
    success = test_navigation()
    if success:
        print("\n[SUCCESS] All navigation links are valid!")
    else:
        print("\n[WARNING] Some navigation links are broken!")