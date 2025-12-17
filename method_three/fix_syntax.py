# Fix the syntax error in scraper.py
with open('scraper.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Insert 'try:' after line 2429 (if __name__ == "__main__":)
# Line 2429 is index 2428 (0-indexed)
lines.insert(2429, '    try:\n')

# Indent the next line (# Check if we should run in distributed mode)
# After insertion, this is now at index 2430
for i in range(2430, len(lines)):
    if lines[i].startswith('    finally:'):
        # Found the finally block, stop indenting
        break
    # Add 4 spaces of indentation
    if lines[i].strip():  # Only indent non-empty lines
        lines[i] = '    ' + lines[i]

with open('scraper.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fixed syntax error in scraper.py")
