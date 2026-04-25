# Overview

This repository contains a game, based on combining Wordle with Ark Nova.

A random animal is chosen, and a user is asked to guess the animal within 8 tries, based on clues about:
 * Cost
 * Size
 * Tags
 * Continents
 * Appeal Value
 * Conversation Value
 
# File Layout
 - index.html contains the raw page and most of the logic besides the animals list.
 - animals.js contains the data about the animals to choose from, hooked into index.js
 - src/ contains the data that generated index.html, and the scripts to parse it.
 
# Source data
The data in src/arknovaanimals_VM_v2.xlsx is downloaded from the internet, and is close to correct but contains some errors. The script in src/parse_animals.py takes that data and combines it with our known errors list to produce raw_animals.tsv.

raw_animals.tsv can be trivially converted into animals.js, which is what the site actually uses.