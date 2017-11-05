rm data/*.json

../../dwig/dwig.py -pp -cd  2 -tl -rs 0 -os ran > data/ran1_1.json
../../dwig/dwig.py -pp -cd 12 -tl -rs 0 -os ran > data/ran1_2.json

../../dwig/dwig.py -pp -cd  2 -tl -rs 0 -os ran -f > data/ranf1_1.json

../../dwig/dwig.py -pp -cd  2 -tl -rs 0 -os const -cp -1.0 > data/const_1.json
../../dwig/dwig.py -pp -cd 12 -tl -rs 0 -os const -cp -1.0 > data/const_2.json

../../dwig/dwig.py -pp -cd  2 -tl -rs 0 -os const -cp -0.05 > data/const_3.json
../../dwig/dwig.py -pp -cd 12 -tl -rs 0 -os const -cp -0.05 > data/const_4.json
