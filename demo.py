import csv,json,random
from pathlib import Path
p=Path('data');p.mkdir(exist_ok=True);rng=random.Random(44)
with (p/'demo.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['date','symbol','score','return'])
 for m in range(2000*12,2026*12):
  for i in range(30):w.writerow([f'{m//12}-{m%12+1:02}-01',f'S{i:02}',rng.uniform(0.3,1),rng.gauss(0.005,0.07)])
(p/'demo.manifest.json').write_text(json.dumps({'kind':'synthetic','source':'seed44 noise'}))
