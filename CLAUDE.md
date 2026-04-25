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