FTFL detector hardening batch

Replace these files in the repository:
  tools/detect_code_switches.py
  reference/glossaries/german_signals.txt

Then run:
  python .\tools\detect_code_switches.py

This batch preserves multi-language ambiguity, adds strong/weak/shared evidence,
and removes common English/German homographs such as 'was', 'man', 'also',
'die', and standalone 'von' from German detection.
