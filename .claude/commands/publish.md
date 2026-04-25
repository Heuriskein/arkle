When requested, to publish changes to the new website:

 1. prepare a git commit with a reasonable message, and get permission from the user to commit it
 1. prepare and commit another git commit that increases the minor version number in the header inside index.html
 1. give the user a list of commits that will be pushed if we perform a git push, and get permission from the user to push it
 1. push the commits to the repo
 
At this point, git pages will update the website. Poll the website once every 30s until you see the new version number appear before completing this skill. To bypass the WebFetch cache, append a unique query parameter each poll using the new version number and a timestamp, e.g. https://heuriskein.github.io/arkle/?v=0.2&t=1714000000. GitHub Pages ignores unknown query params so the page loads correctly.